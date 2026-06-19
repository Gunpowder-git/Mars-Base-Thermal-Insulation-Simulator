import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.collections import PatchCollection
import matplotlib.animation as animation
from matplotlib.colors import LinearSegmentedColormap
import warnings
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import json
import csv
from datetime import datetime
import pickle

warnings.filterwarnings('ignore')
plt.rcParams['font.sans-serif'] = ['SimHei']

class MaterialLibrary:
    """材料库管理"""

    def __init__(self):
        self.materials = {
            'air': {'name': '空气', 'alpha': 0.15, 'cost': 0, 'density': 1.2, 'color': '#E8F4F8'},
            'concrete': {'name': '混凝土', 'alpha': 0.008, 'cost': 100, 'density': 2400, 'color': '#808080'},
            'foam': {'name': '保温泡沫', 'alpha': 0.001, 'cost': 300, 'density': 50, 'color': '#D2691E'},
            'aerogel': {'name': '气凝胶', 'alpha': 0.0003, 'cost': 500, 'density': 20, 'color': '#DAA520'},
            'ceramic': {'name': '陶瓷', 'alpha': 0.002, 'cost': 200, 'density': 1200, 'color': '#A0522D'},
            'metal_insulation': {'name': '金属绝缘', 'alpha': 0.0005, 'cost': 400, 'density': 100, 'color': '#C0C0C0'},
            'vacuum': {'name': '真空', 'alpha': 0.0001, 'cost': 1000, 'density': 0, 'color': '#1a1a2e'},
            'copper': {'name': '铜导热层', 'alpha': 0.12, 'cost': 600, 'density': 8960, 'color': '#B87333'},
        }

        # 映射ID到材料名
        self.id_to_material = {i: name for i, name in enumerate(self.materials.keys())}
        self.material_to_id = {name: i for i, name in enumerate(self.materials.keys())}

class MarsEnvironment:
    """火星环境模拟"""

    def __init__(self):
        self.surface_temperature_range = (-80, 20)  # 火星表面温度范围
        self.atmospheric_pressure = 0.006  # 地球大气压的0.6%
        self.radiation_multiplier = 1.5  # 辐射强度倍数
        self.dust_storm_probability = 0.3  # 沙尘暴概率
        self.thermal_cycle_duration = 24  # 热循环周期(小时)

    def get_external_temperature(self, time_step):
        """获取外部温度（考虑火星日夜温差）"""
        # 简化的昼夜温度变化模型
        cycle_position = (time_step % 1000) / 1000 * 2 * np.pi
        avg_temp = (self.surface_temperature_range[0] + self.surface_temperature_range[1]) / 2
        temp_variation = (self.surface_temperature_range[1] - self.surface_temperature_range[0]) / 2
        return avg_temp + temp_variation * np.sin(cycle_position)

class ThermalCellularAutomaton:
    """热传导元胞自动机模拟器"""

    def __init__(self, width=100, height=60, dx=0.01, material_lib=None, mars_env=None):
        self.width = width
        self.height = height
        self.dx = dx
        self.material_lib = material_lib or MaterialLibrary()
        self.mars_env = mars_env or MarsEnvironment()

        # 温度场 [height, width]
        self.T = np.zeros((height, width), dtype=np.float32)

        # 材料场
        self.material = np.zeros((height, width), dtype=np.int32)

        # 材料属性定义（从材料库获取）
        self.material_props = {}
        for mat_name, props in self.material_lib.materials.items():
            self.material_props[self.material_lib.material_to_id[mat_name]] = {
                'name': props['name'],
                'alpha': props['alpha'],
                'color': props['color'],
                'density': props['density'],
                'cost': props['cost']
            }

        # 时间步长（根据CFL条件自动计算）
        max_alpha = max(p['alpha'] for p in self.material_props.values())
        self.dt = 0.2 * (dx**2) / max_alpha

        # 边界条件设置
        self.left_temp = 20.0   # 室内温度 (°C)
        self.heat_source_temp = 50.0  # 热源温度

        # 初始化几何结构
        self._setup_initial_geometry()

        # 历史记录
        self.time_history = []
        self.heat_loss_history = []
        self.room_temp_history = []
        self.wall_temp_history = []

    def _setup_initial_geometry(self):
        """设置初始几何结构"""
        # 默认简单墙体结构
        room_end = int(self.width * 0.2)
        wall_start = room_end
        wall_end = int(self.width * 0.7)
        vacuum_start = wall_end

        # 设置初始温度
        self.T[:, :room_end] = self.left_temp
        for i in range(wall_start, wall_end):
            ratio = (i - wall_start) / (wall_end - wall_start)
            self.T[:, i] = self.left_temp + ratio * (self.mars_env.surface_temperature_range[0] - self.left_temp)
        self.T[:, vacuum_start:] = self.mars_env.surface_temperature_range[0]

        # 设置默认材料
        self.material[:, :room_end] = self.material_lib.material_to_id['air']
        self.material[:, wall_start:wall_end] = self.material_lib.material_to_id['concrete']
        self.material[:, vacuum_start:] = self.material_lib.material_to_id['vacuum']

        # 热源区域
        center_y = self.height // 2
        center_x = room_end // 2
        self.heat_source_mask = np.zeros_like(self.T, dtype=bool)
        self.heat_source_mask[center_y-3:center_y+3, center_x-3:center_x+3] = True
        self.T[center_y-3:center_y+3, center_x-3:center_x+3] = self.heat_source_temp

    def update_boundary_conditions(self, time_step):
        """应用边界条件"""
        # 左边界：房间恒温
        self.T[:, 0] = self.left_temp

        # 右边界：火星环境温度
        external_temp = self.mars_env.get_external_temperature(time_step)
        self.T[:, -1] = external_temp

        # 上下边界：绝热
        self.T[0, :] = self.T[1, :]
        self.T[-1, :] = self.T[-2, :]

        # 热源区域：保持恒温
        self.T[self.heat_source_mask] = self.heat_source_temp

    def update_with_defects(self):
        """考虑缺陷的更新（热桥等）"""
        # 在实际应用中可以添加热桥、裂缝等缺陷
        pass

    def step(self, time_step):
        """执行一个时间步长的演化"""
        T_new = self.T.copy()

        # 内部网格点更新
        for i in range(1, self.height-1):
            for j in range(1, self.width-1):
                mat_id = self.material[i, j]
                alpha = self.material_props[mat_id]['alpha']

                # 热传导方程离散形式
                laplacian = (self.T[i+1, j] + self.T[i-1, j] +
                            self.T[i, j+1] + self.T[i, j-1] - 4*self.T[i, j]) / (self.dx**2)

                T_new[i, j] = self.T[i, j] + alpha * self.dt * laplacian

        self.T = T_new
        self.update_boundary_conditions(time_step)
        self.update_with_defects()

        # 记录统计数据
        room_region = self.T[:, :int(self.width*0.2)]
        wall_region = self.T[:, int(self.width*0.2):int(self.width*0.7)]

        self.room_temp_history.append(np.mean(room_region))
        self.wall_temp_history.append(np.mean(wall_region))

        return self.T

    def calculate_performance_metrics(self):
        """计算性能指标"""
        room_region = self.T[:, :int(self.width*0.2)]
        wall_region = self.T[:, int(self.width*0.2):int(self.width*0.7)]

        # 计算材料总成本
        total_cost = 0
        for mat_id, props in self.material_props.items():
            mask = (self.material == mat_id)
            total_cost += np.sum(mask) * props['cost'] / 1000  # 标准化单位

        # 计算墙体重量
        total_weight = 0
        for mat_id, props in self.material_props.items():
            mask = (self.material == mat_id)
            total_weight += np.sum(mask) * props['density'] / 1000  # 标准化单位

        metrics = {
            'room_avg_temp': np.mean(room_region),
            'room_std_temp': np.std(room_region),
            'wall_avg_temp': np.mean(wall_region),
            'wall_max_temp': np.max(wall_region),
            'wall_min_temp': np.min(wall_region),
            'total_energy': np.sum(self.T),
            'total_cost': total_cost,
            'total_weight': total_weight,
            'heat_loss_rate': abs(np.mean(room_region) - self.left_temp),
            'temperature_stability': np.std(room_region),
            'r_value_approx': 1.0 / (np.mean(np.abs(self.T[:, -2] - self.T[:, -1])) + 0.001)  # 简化的R值估计
        }
        return metrics

    def design_wall(self, layer_config):
        """根据配置设计墙体层结构"""
        room_end = int(self.width * 0.2)
        wall_start = room_end
        wall_end = int(self.width * 0.7)

        # 清空墙体区域
        self.material[:, wall_start:wall_end] = self.material_lib.material_to_id['air']

        # 按照配置设置各层
        if len(layer_config) > 0:
            layer_width = (wall_end - wall_start) // len(layer_config)
            for i, mat_name in enumerate(layer_config):
                start_idx = wall_start + i * layer_width
                end_idx = min(wall_start + (i+1) * layer_width, wall_end)
                if mat_name in self.material_lib.material_to_id:
                    self.material[:, start_idx:end_idx] = self.material_lib.material_to_id[mat_name]

    def add_defect(self, defect_type, position, size):
        """添加缺陷"""
        y, x = position
        h, w = size

        if defect_type == 'thermal_bridge':
            # 铜制热桥
            self.material[y:y+h, x:x+w] = self.material_lib.material_to_id['copper']
        elif defect_type == 'crack':
            # 裂缝（增加热传导）
            self.material[y:y+h, x:x+w] = self.material_lib.material_to_id['air']

class InteractiveThermalSimulation:
    """交互式可视化界面"""

    def __init__(self, sim):
        self.sim = sim
        self.fig, self.axes = plt.subplots(2, 2, figsize=(14, 10))
        self.fig.patch.set_facecolor('#f0f0f0')

        # 自定义温度colormap
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
        self.ax_main.set_title('火星基地隔热墙温度场分布 (°C)', fontsize=12, fontweight='bold')
        self.ax_main.set_xlabel('水平位置 (元胞)')
        self.ax_main.set_ylabel('垂直位置 (元胞)')

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

        # 材料分布图
        self.ax_material = self.axes[1, 0]
        mat_colors = [props['color'] for id, props in self.sim.material_props.items()]
        mat_cmap = LinearSegmentedColormap.from_list('materials', mat_colors)
        self.im_mat = self.ax_material.imshow(self.sim.material, cmap=mat_cmap,
                                              aspect='auto')
        self.ax_material.set_title('材料分布图', fontsize=11)

        # 统计信息
        self.ax_stats = self.axes[1, 1]
        self.ax_stats.axis('off')
        self.text_stats = self.ax_stats.text(0.1, 0.9, '', transform=self.ax_stats.transAxes,
                                            fontsize=9, verticalalignment='top',
                                            fontfamily='monospace',
                                            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

        plt.tight_layout()

    def animate(self, frame):
        """动画更新函数"""
        # 执行多个时间步以加速模拟
        for i in range(5):
            self.sim.step(frame * 5 + i)

        # 更新温度场
        self.im.set_array(self.sim.T)

        # 更新剖面图
        center_y = self.sim.height // 2
        x_data = np.arange(self.sim.width)
        y_data = self.sim.T[center_y, :]
        self.line_profile.set_data(x_data, y_data)

        # 更新统计信息
        metrics = self.sim.calculate_performance_metrics()
        info_text = (
            f"时间步: {frame * 5}\n"
            f"房间平均温度: {metrics['room_avg_temp']:.2f}°C\n"
            f"房间温度波动: ±{metrics['temperature_stability']:.2f}°C\n"
            f"墙体平均温度: {metrics['wall_avg_temp']:.2f}°C\n"
            f"热损失率: {metrics['heat_loss_rate']:.3f}\n"
            f"系统总能量: {metrics['total_energy']:.2e}\n"
            f"总成本: ${metrics['total_cost']:.2f}\n"
            f"总重量: {metrics['total_weight']:.2f}kg\n"
            f"近似R值: {metrics['r_value_approx']:.3f}"
        )
        self.text_stats.set_text(info_text)

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

class ThermalDesignStudio:
    """热设计工作室主界面"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("火星基地多材料隔热墙优化竞赛 - 设计工作室")
        self.root.geometry("1200x800")

        # 初始化仿真对象
        self.material_lib = MaterialLibrary()
        self.mars_env = MarsEnvironment()
        self.sim = ThermalCellularAutomaton(material_lib=self.material_lib, mars_env=self.mars_env)
        self.vis = None

        self.create_widgets()

    def create_widgets(self):
        """创建界面组件"""
        # 主框架
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 控制面板
        control_frame = ttk.LabelFrame(main_frame, text="控制面板", padding=10)
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        # 材料选择
        ttk.Label(control_frame, text="墙体材料层配置:").pack(anchor=tk.W)

        # 创建材料选择列表
        self.layer_vars = []
        for i in range(5):  # 最多5层
            frame = ttk.Frame(control_frame)
            frame.pack(fill=tk.X, pady=2)

            ttk.Label(frame, text=f"第{i+1}层:").pack(side=tk.LEFT)
            var = tk.StringVar(value='concrete')  # 默认值
            combo = ttk.Combobox(frame, textvariable=var, values=list(self.material_lib.materials.keys()), width=12)
            combo.pack(side=tk.LEFT, padx=(5, 0))
            self.layer_vars.append(var)

        # 缺陷添加选项
        ttk.Label(control_frame, text="缺陷模拟:").pack(anchor=tk.W, pady=(10, 0))

        defect_frame = ttk.Frame(control_frame)
        defect_frame.pack(fill=tk.X)

        self.defect_var = tk.StringVar(value='none')
        defect_combo = ttk.Combobox(defect_frame, textvariable=self.defect_var,
                                   values=['none', 'thermal_bridge', 'crack'], width=12)
        defect_combo.pack(side=tk.LEFT)

        ttk.Button(defect_frame, text="添加缺陷", command=self.add_defect).pack(side=tk.LEFT, padx=(5, 0))

        # 设计应用按钮
        ttk.Button(control_frame, text="应用设计", command=self.apply_design).pack(fill=tk.X, pady=10)
        ttk.Button(control_frame, text="运行仿真", command=self.run_simulation).pack(fill=tk.X, pady=5)
        ttk.Button(control_frame, text="生成报告", command=self.generate_report).pack(fill=tk.X, pady=5)
        ttk.Button(control_frame, text="保存设计", command=self.save_design).pack(fill=tk.X, pady=5)
        ttk.Button(control_frame, text="加载设计", command=self.load_design).pack(fill=tk.X, pady=5)

        # 图表显示区域
        self.plot_frame = ttk.Frame(main_frame)
        self.plot_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 结果显示区域
        self.result_frame = ttk.LabelFrame(main_frame, text="仿真结果", padding=10)
        self.result_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=0, pady=(10, 0))

        self.result_text = tk.Text(self.result_frame, height=8)
        scrollbar = ttk.Scrollbar(self.result_frame, orient=tk.VERTICAL, command=self.result_text.yview)
        self.result_text.configure(yscrollcommand=scrollbar.set)

        self.result_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def apply_design(self):
        """应用设计"""
        layer_config = []
        for var in self.layer_vars:
            mat_name = var.get()
            if mat_name != '':  # 忽略空值
                layer_config.append(mat_name)

        if layer_config:
            self.sim.design_wall(layer_config)
            self.result_text.insert(tk.END, f"已应用设计: {layer_config}\n")
            self.result_text.see(tk.END)

    def add_defect(self):
        """添加缺陷"""
        defect_type = self.defect_var.get()
        if defect_type != 'none':
            # 简单的随机位置添加缺陷
            y = np.random.randint(10, self.sim.height-10)
            x = np.random.randint(int(self.sim.width*0.3), int(self.sim.width*0.6))
            h, w = 5, 10

            self.sim.add_defect(defect_type, (y, x), (h, w))
            self.result_text.insert(tk.END, f"已添加缺陷: {defect_type} 在位置 ({y}, {x})\n")
            self.result_text.see(tk.END)

    def run_simulation(self):
        """运行仿真"""
        self.result_text.insert(tk.END, "开始运行热传导仿真...\n")

        # 创建可视化对象（如果不存在）
        if self.vis is None:
            self.vis = InteractiveThermalSimulation(self.sim)

        # 启动动画
        self.vis.run(frames=200, interval=50)

        # 更新结果显示
        metrics = self.sim.calculate_performance_metrics()
        result_str = f"\n仿真完成！性能指标：\n"
        result_str += f"- 房间平均温度: {metrics['room_avg_temp']:.2f}°C\n"
        result_str += f"- 温度稳定性: ±{metrics['temperature_stability']:.2f}°C\n"
        result_str += f"- 热损失率: {metrics['heat_loss_rate']:.3f}\n"
        result_str += f"- 总成本: ${metrics['total_cost']:.2f}\n"
        result_str += f"- 总重量: {metrics['total_weight']:.2f}kg\n"
        result_str += f"- 近似R值: {metrics['r_value_approx']:.3f}\n\n"

        self.result_text.insert(tk.END, result_str)
        self.result_text.see(tk.END)

    def generate_report(self):
        """生成报告"""
        metrics = self.sim.calculate_performance_metrics()

        report = f"""
火星基地多材料隔热墙设计方案报告
================================
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
================================

性能指标:
- 房间平均温度: {metrics['room_avg_temp']:.2f}°C
- 房间温度稳定性: ±{metrics['temperature_stability']:.2f}°C
- 墙体平均温度: {metrics['wall_avg_temp']:.2f}°C
- 墙体最高温度: {metrics['wall_max_temp']:.2f}°C
- 墙体最低温度: {metrics['wall_min_temp']:.2f}°C
- 热损失率: {metrics['heat_loss_rate']:.3f}
- 近似R值: {metrics['r_value_approx']:.3f}

经济指标:
- 总成本: ${metrics['total_cost']:.2f}
- 总重量: {metrics['total_weight']:.2f}kg

综合评价:
- 保温性能: {'优秀' if metrics['temperature_stability'] < 2 else '良好' if metrics['temperature_stability'] < 5 else '需改进'}
- 成本效益: {'优秀' if metrics['total_cost'] < 500 else '良好' if metrics['total_cost'] < 1000 else '较高'}
- 适用性: {'适合长期居住' if abs(metrics['room_avg_temp'] - 20) < 2 else '需要额外调节'}

推荐等级: {self.calculate_grade(metrics)}
        """.strip()

        self.result_text.insert(tk.END, report + "\n\n")
        self.result_text.see(tk.END)

        # 弹窗显示报告
        messagebox.showinfo("分析报告", report)

    def calculate_grade(self, metrics):
        """计算推荐等级"""
        temp_score = 10 - min(abs(metrics['room_avg_temp'] - 20), 10)  # 温度接近20°C的程度
        stability_score = 10 - min(metrics['temperature_stability'] * 2, 10)  # 温度稳定性
        loss_score = 10 - min(metrics['heat_loss_rate'] * 5, 10)  # 热损失
        cost_score = max(0, 10 - metrics['total_cost'] / 100)  # 成本

        avg_score = (temp_score + stability_score + loss_score + cost_score) / 4

        if avg_score >= 8:
            return "S级 - 最优设计"
        elif avg_score >= 6:
            return "A级 - 优秀设计"
        elif avg_score >= 4:
            return "B级 - 良好设计"
        else:
            return "C级 - 需要优化"

    def save_design(self):
        """保存设计"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".tds",
            filetypes=[("Thermal Design Studio files", "*.tds"), ("All files", "*.*")]
        )

        if filename:
            design_data = {
                'layers': [var.get() for var in self.layer_vars],
                'material_grid': self.sim.material.copy(),
                'temperature_grid': self.sim.T.copy(),
                'timestamp': datetime.now().isoformat()
            }

            with open(filename, 'wb') as f:
                pickle.dump(design_data, f)

            self.result_text.insert(tk.END, f"设计已保存到: {filename}\n")
            self.result_text.see(tk.END)

    def load_design(self):
        """加载设计"""
        filename = filedialog.askopenfilename(
            filetypes=[("Thermal Design Studio files", "*.tds"), ("All files", "*.*")]
        )

        if filename:
            try:
                with open(filename, 'rb') as f:
                    design_data = pickle.load(f)

                # 恢复材料布局
                self.sim.material = design_data['material_grid'].copy()
                self.sim.T = design_data['temperature_grid'].copy()

                # 恢复层数配置
                layers = design_data['layers']
                for i, layer in enumerate(layers):
                    if i < len(self.layer_vars):
                        self.layer_vars[i].set(layer)

                self.result_text.insert(tk.END, f"设计已从 {filename} 加载\n")
                self.result_text.see(tk.END)

            except Exception as e:
                messagebox.showerror("错误", f"加载设计失败: {str(e)}")

    def run(self):
        """运行主界面"""
        self.root.mainloop()

def main():
    """主函数"""
    print("火星基地多材料隔热墙优化竞赛 - 热设计工作室")
    print("=" * 60)
    print("特性:")
    print("- 多材料库支持（混凝土、保温泡沫、气凝胶等）")
    print("- 火星环境模拟（温度变化、辐射等）")
    print("- 缺陷建模（热桥、裂缝等）")
    print("- 性能指标评估")
    print("- 可视化设计界面")
    print("- 报告生成与设计保存")
    print("=" * 60)

    # 启动GUI
    app = ThermalDesignStudio()
    app.run()

if __name__ == "__main__":
    main()