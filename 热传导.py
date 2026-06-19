import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.collections import PatchCollection
import matplotlib.animation as animation
from matplotlib.colors import LinearSegmentedColormap
import warnings
warnings.filterwarnings('ignore')
plt.rcParams['font.sans-serif'] = ['SimHei']  # 设置字体为黑体（解决无法输出汉字字符的问题）

class ThermalCellularAutomaton:
    """
    热传导元胞自动机模拟器
    物理模型：基于二维热扩散方程的离散化
    """
    
    def __init__(self, width=100, height=60, dx=0.01):
        """
        初始化模拟网格
        
        Parameters:
        -----------
        width : int
            网格宽度（对应x方向，从左到右：房间->墙体->真空）
        height : int
            网格高度
        dx : float
            空间步长（用于计算稳定性）
        """
        self.width = width
        self.height = height
        self.dx = dx
        
        # 温度场 [height, width]
        self.T = np.zeros((height, width), dtype=np.float32)
        
        # 材料场：0=空气(室内), 1=墙体材料A, 2=墙体材料B, 3=真空(室外)
        self.material = np.zeros((height, width), dtype=np.int32)
        
        # 材料属性定义
        # 热扩散系数 alpha (m²/s 量级，此处为归一化值)
        # 热容系数 (影响温度变化速率)
        self.material_props = {
            0: {'name': '室内空气', 'alpha': 0.15, 'color': '#E8F4F8', 'density': 1.2},  # 空气
            1: {'name': '混凝土', 'alpha': 0.008, 'color': '#808080', 'density': 2400},    # 混凝土（低扩散）
            2: {'name': '保温泡沫', 'alpha': 0.001, 'color': '#D2691E', 'density': 50},    # 保温材料（极低扩散）
            3: {'name': '真空/太空', 'alpha': 0.0001, 'color': '#1a1a2e', 'density': 0},   # 近似绝热
            4: {'name': '铜导热层', 'alpha': 0.12, 'color': '#B87333', 'density': 8960},   # 金属（高扩散）
        }
        
        # 时间步长（根据CFL条件自动计算）
        max_alpha = max(p['alpha'] for p in self.material_props.values())
        self.dt = 0.2 * (dx**2) / max_alpha  # 安全因子0.2
        
        # 边界条件设置
        self.left_temp = 20.0   # 室内温度 (°C)
        self.right_temp = -80.0 # 外部太空温度 (°C)
        self.heat_source_temp = 50.0  # 热源温度
        
        # 初始化几何结构
        self._setup_geometry()
        
        # 历史记录
        self.time_history = []
        self.heat_loss_history = []
        
    def _setup_geometry(self):
        """
        设置初始几何结构：
        [左边界:房间(20°C)] [中间:复合墙体] [右边界:真空(-80°C)]
        """
        # 定义区域边界（x坐标）
        room_end = int(self.width * 0.2)      # 房间占20%
        wall_start = room_end
        wall_end = int(self.width * 0.7)      # 墙体占50%
        vacuum_start = wall_end
        
        # 创建温度初始场
        # 房间区域：恒温20°C
        self.T[:, :room_end] = self.left_temp
        
        # 墙体区域：初始温度梯度从20°C线性下降到-80°C
        for i in range(wall_start, wall_end):
            ratio = (i - wall_start) / (wall_end - wall_start)
            self.T[:, i] = self.left_temp + ratio * (self.right_temp - self.left_temp)
        
        # 真空区域：-80°C
        self.T[:, vacuum_start:] = self.right_temp
        
        # 设置材料类型
        # 房间：空气
        self.material[:, :room_end] = 0
        
        # 墙体：多层材料设计（可以自定义）
        # 内层：混凝土 中层：保温层 外层：混凝土
        wall_third = (wall_end - wall_start) // 3
        
        self.material[:, wall_start:wall_start+wall_third] = 1  # 混凝土内层
        self.material[:, wall_start+wall_third:wall_end-wall_third] = 2  # 保温层
        self.material[:, wall_end-wall_third:wall_end] = 1  # 混凝土外层
        
        # 添加一个"热桥"缺陷（可选）：贯穿墙体的金属条
        bridge_y_start = int(self.height * 0.4)
        bridge_y_end = int(self.height * 0.6)
        self.material[bridge_y_start:bridge_y_end, wall_start+5:wall_end-5] = 4
        
        # 真空：空气（但会被特殊处理为低温边界）
        self.material[:, vacuum_start:] = 3
        
        # 在房间中心添加一个持续热源（模拟暖气或设备）
        center_y = self.height // 2
        center_x = room_end // 2
        self.heat_source_pos = (center_y, center_x)
        self.T[center_y-3:center_y+3, center_x-3:center_x+3] = self.heat_source_temp
        
        # 记录热源区域（持续加热）
        self.heat_source_mask = np.zeros_like(self.T, dtype=bool)
        self.heat_source_mask[center_y-3:center_y+3, center_x-3:center_x+3] = True
        
    def update_boundary_conditions(self):
        """应用边界条件"""
        # 左边界：房间恒温20°C（ Dirichlet边界）
        self.T[:, 0] = self.left_temp
        
        # 右边界：真空，辐射散热（Newton冷却定律近似）
        # 这里简化为固定温度，也可以改为辐射边界
        self.T[:, -1] = self.right_temp
        
        # 上下边界：绝热（Neumann边界，零梯度）
        self.T[0, :] = self.T[1, :]
        self.T[-1, :] = self.T[-2, :]
        
        # 热源区域：保持恒定高温（模拟持续加热的设备）
        self.T[self.heat_source_mask] = self.heat_source_temp
        
    def step(self):
        """
        执行一个时间步长的演化
        使用显式有限差分法求解热传导方程
        """
        T_new = self.T.copy()
        
        # 内部网格点更新（跳过边界）
        for i in range(1, self.height-1):
            for j in range(1, self.width-1):
                # 获取当前材料属性
                mat_id = self.material[i, j]
                alpha = self.material_props[mat_id]['alpha']
                
                # 热传导方程离散形式（二维拉普拉斯算子）
                # ∇²T ≈ (T[i+1,j] + T[i-1,j] + T[i,j+1] + T[i,j-1] - 4*T[i,j]) / dx²
                laplacian = (self.T[i+1, j] + self.T[i-1, j] + 
                            self.T[i, j+1] + self.T[i, j-1] - 4*self.T[i, j]) / (self.dx**2)
                
                # 更新温度：T_new = T_old + alpha * dt * laplacian
                # 注意：不同材料在界面处的处理（这里使用简化模型）
                T_new[i, j] = self.T[i, j] + alpha * self.dt * laplacian
        
        self.T = T_new
        
        # 应用边界条件
        self.update_boundary_conditions()
        
        # 计算热流损失（通过右边界）
        heat_loss = np.sum((self.T[:, -2] - self.T[:, -1]) / self.dx) * self.dt
        self.heat_loss_history.append(heat_loss)
        
        return self.T
    
    def get_temperature_stats(self):
        """获取统计信息"""
        room_region = self.T[:, :int(self.width*0.2)]
        wall_region = self.T[:, int(self.width*0.2):int(self.width*0.7)]
        
        return {
            'room_avg': np.mean(room_region),
            'room_std': np.std(room_region),
            'wall_max': np.max(wall_region),
            'wall_min': np.min(wall_region),
            'total_energy': np.sum(self.T)
        }

class InteractiveThermalSimulation:
    """交互式可视化界面"""
    
    def __init__(self, sim):
        self.sim = sim
        self.fig, self.axes = plt.subplots(2, 2, figsize=(14, 10))
        self.fig.patch.set_facecolor('#f0f0f0')
        
        # 自定义温度colormap：深蓝(冷) -> 青 -> 绿 -> 黄 -> 红(热)
        colors = ['#1a1a2e', '#16213e', '#0f3460', '#e94560', '#ff9f45', '#fcbf49']
        self.cmap = LinearSegmentedColormap.from_list('thermal', colors)
        
        self.setup_plots()
        self.frame_count = 0
        
    def setup_plots(self):
        """初始化图表布局"""
        # 主图：温度场热力图
        self.ax_main = self.axes[0, 0]
        self.im = self.ax_main.imshow(self.sim.T, cmap=self.cmap, 
                                      vmin=-100, vmax=100, aspect='auto',
                                      interpolation='bilinear')
        self.ax_main.set_title('温度场分布 (°C)\n左:房间(20°C) | 中:复合墙体 | 右:真空(-80°C)', 
                              fontsize=12, fontweight='bold')
        self.ax_main.set_xlabel('水平位置 (元胞)')
        self.ax_main.set_ylabel('垂直位置 (元胞)')
        
        # 添加材料分界线标注
        room_end = int(self.sim.width * 0.2)
        wall_end = int(self.sim.width * 0.7)
        self.ax_main.axvline(x=room_end, color='white', linestyle='--', alpha=0.5)
        self.ax_main.axvline(x=wall_end, color='white', linestyle='--', alpha=0.5)
        
        # 添加颜色条
        cbar = plt.colorbar(self.im, ax=self.ax_main, fraction=0.046)
        cbar.set_label('温度 (°C)', rotation=270, labelpad=20)
        
        # 剖面图：水平中心线温度分布
        self.ax_profile = self.axes[0, 1]
        center_y = self.sim.height // 2
        self.line_profile, = self.ax_profile.plot([], [], 'w-', linewidth=2, label='实际温度')
        self.ax_profile.axhline(y=20, color='r', linestyle='--', alpha=0.5, label='目标温度(20°C)')
        self.ax_profile.set_xlim(0, self.sim.width)
        self.ax_profile.set_ylim(-100, 100)
        self.ax_profile.set_title('墙体中心水平剖面温度分布', fontsize=11)
        self.ax_profile.set_xlabel('水平位置')
        self.ax_profile.set_ylabel('温度 (°C)')
        self.ax_profile.legend()
        self.ax_profile.grid(True, alpha=0.3)
        
        # 标记区域
        self.ax_profile.axvspan(0, room_end, alpha=0.2, color='green', label='房间')
        self.ax_profile.axvspan(room_end, wall_end, alpha=0.2, color='gray', label='墙体')
        self.ax_profile.axvspan(wall_end, self.sim.width, alpha=0.2, color='blue', label='真空')
        
        # 材料分布图
        self.ax_material = self.axes[1, 0]
        mat_colors = [p['color'] for p in self.sim.material_props.values()]
        mat_cmap = LinearSegmentedColormap.from_list('materials', mat_colors)
        self.im_mat = self.ax_material.imshow(self.sim.material, cmap=mat_cmap, 
                                              aspect='auto', vmin=0, vmax=4)
        self.ax_material.set_title('材料分布图\n(灰:混凝土 棕:保温层 黑:真空 铜:热桥)', fontsize=11)
        
        # 统计信息
        self.ax_stats = self.axes[1, 1]
        self.ax_stats.axis('off')
        self.text_stats = self.ax_stats.text(0.1, 0.9, '', transform=self.ax_stats.transAxes,
                                            fontsize=10, verticalalignment='top',
                                            fontfamily='monospace',
                                            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
        plt.tight_layout()
        
    def animate(self, frame):
        """动画更新函数"""
        # 执行多个时间步以加速模拟
        for _ in range(5):
            self.sim.step()
        
        # 更新温度场
        self.im.set_array(self.sim.T)
        
        # 更新剖面图
        center_y = self.sim.height // 2
        x_data = np.arange(self.sim.width)
        y_data = self.sim.T[center_y, :]
        self.line_profile.set_data(x_data, y_data)
        
        # 更新统计信息
        stats = self.sim.get_temperature_stats()
        info_text = (
            f"时间步: {frame * 5}\n"
            f"房间平均温度: {stats['room_avg']:.2f}°C\n"
            f"房间温度波动: ±{stats['room_std']:.2f}°C\n"
            f"墙体最高温度: {stats['wall_max']:.2f}°C\n"
            f"墙体最低温度: {stats['wall_min']:.2f}°C\n"
            f"系统总能量: {stats['total_energy']:.2e}\n\n"
            f"材料legend:\n"
            f"0: 室内空气 (α=0.15)\n"
            f"1: 混凝土 (α=0.008)\n"
            f"2: 保温泡沫 (α=0.001)\n"
            f"3: 真空 (α=0.0001)\n"
            f"4: 铜导热层 (α=0.12) ← 热桥"
        )
        self.text_stats.set_text(info_text)
        
        # 动态调整颜色范围以适应数据（可选）
        # self.im.set_clim(vmin=self.sim.T.min(), vmax=self.sim.T.max())
        
        self.frame_count += 1
        return [self.im, self.line_profile, self.text_stats]
    
    def run(self, frames=200, interval=50):
        """运行动画"""
        self.anim = animation.FuncAnimation(
            self.fig, self.animate, frames=frames,
            interval=interval, blit=True, repeat=True
        )
        plt.show()
        return self.anim

def run_static_analysis():
    """
    运行静态分析版本（不带动画，适合保存结果图）
    """
    sim = ThermalCellularAutomaton(width=120, height=80)
    vis = InteractiveThermalSimulation(sim)
    
    # 手动推进模拟到稳态附近
    print("正在模拟热传导过程...")
    for i in range(1000):
        sim.step()
        if i % 100 == 0:
            print(f"步骤 {i}/1000")
    
    # 更新最终显示
    vis.im.set_array(sim.T)
    stats = sim.get_temperature_stats()
    print(f"\n最终统计:\n{stats}")
    
    # 保存图片
    plt.savefig('thermal_simulation_result.png', dpi=150, bbox_inches='tight')
    print("结果已保存为 thermal_simulation_result.png")
    plt.show()

# 主程序入口
if __name__ == "__main__":
    import sys
    
    print("热传导元胞自动机模拟")
    print("=" * 50)
    print("1. 运行动画演示 (实时可视化)")
    print("2. 运行静态分析 (快速到稳态并保存图片)")
    print("=" * 50)
    
    choice = input("请选择模式 (1/2): ").strip()
    
    if choice == "2":
        run_static_analysis()
    else:
        # 运行动画版本
        sim = ThermalCellularAutomaton(width=100, height=60)
        vis = InteractiveThermalSimulation(sim)
        print("正在启动动画窗口...")
        print("提示: 红色区域为热源，注意观察热量如何通过铜质热桥快速传导！")
        vis.run(frames=300, interval=50)