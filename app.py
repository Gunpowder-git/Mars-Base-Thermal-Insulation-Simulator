"""
火星基地隔热墙优化 — Flask Web 应用
"""
import sys
import os
import json
import numpy as np
from flask import Flask, jsonify, request, render_template

# ─── 仿真引擎（内嵌，避免依赖 tkinter 文件）────────────────────

class MaterialLibrary:
    def __init__(self):
        self.materials = {
            'air':    {'name':'空气','alpha':0.15,'k':0.026,'cost':0,'density':1.2,'cp':1005,'color':'#E8F4F8'},
            'concrete':{'name':'混凝土','alpha':0.008,'k':1.4,'cost':100,'density':2400,'cp':880,'color':'#808080'},
            'foam':   {'name':'保温泡沫','alpha':0.001,'k':0.035,'cost':300,'density':50,'cp':1500,'color':'#D2691E'},
            'aerogel':{'name':'气凝胶','alpha':0.0003,'k':0.015,'cost':500,'density':20,'cp':1000,'color':'#DAA520'},
            'ceramic':{'name':'陶瓷','alpha':0.002,'k':0.8,'cost':200,'density':1200,'cp':850,'color':'#A0522D'},
            'metal_insulation':{'name':'金属绝缘','alpha':0.0005,'k':0.005,'cost':400,'density':100,'cp':900,'color':'#C0C0C0'},
            'vacuum': {'name':'真空','alpha':0.0001,'k':0.0001,'cost':1000,'density':0,'cp':0,'color':'#1a1a2e'},
            'copper': {'name':'铜导热层','alpha':0.12,'k':400,'cost':600,'density':8960,'cp':385,'color':'#B87333'},
        }
        self.id_to_material = {i: n for i, n in enumerate(self.materials.keys())}
        self.material_to_id = {n: i for i, n in enumerate(self.materials.keys())}

    def get_property_array(self, prop):
        return np.array([self.materials[self.id_to_material[i]][prop]
                         for i in range(len(self.materials))], dtype=np.float32)


class MarsEnvironment:
    def __init__(self):
        self.surface_temperature_range = (-80.0, 20.0)

    def set_temperature_range(self, t_min, t_max):
        self.surface_temperature_range = (float(t_min), float(t_max))

    def get_external_temperature(self, time_step):
        cycle = (time_step % 1000) / 1000 * 2 * np.pi
        avg = (self.surface_temperature_range[0] + self.surface_temperature_range[1]) / 2
        amp = (self.surface_temperature_range[1] - self.surface_temperature_range[0]) / 2
        return avg + amp * np.sin(cycle)


class ThermalSim:
    """热传导元胞自动机（矢量化）"""
    def __init__(self, w=100, h=60, dx=0.01):
        self.width, self.height, self.dx = w, h, dx
        self.lib = MaterialLibrary()
        self.env = MarsEnvironment()
        self.T = np.zeros((h, w), dtype=np.float32)
        self.material = np.zeros((h, w), dtype=np.int32)
        self.alpha = self.lib.get_property_array('alpha')
        self.k_vals = self.lib.get_property_array('k')
        self.density_vals = self.lib.get_property_array('density')
        self.cost_vals = self.lib.get_property_array('cost')
        self.dt = 0.2 * dx**2 / np.max(self.alpha)
        self.left_temp = 20.0
        self.heat_source_temp = 50.0
        self.frame_count = 0
        self._setup_default()

    def _setup_default(self):
        re = int(self.width * 0.2)
        ws, we = re, int(self.width * 0.7)
        self.T[:, :re] = self.left_temp
        for i in range(ws, we):
            self.T[:, i] = self.left_temp + (i - ws) / (we - ws) * (self.env.surface_temperature_range[0] - self.left_temp)
        self.T[:, we:] = self.env.surface_temperature_range[0]
        self.material[:, :re] = self.lib.material_to_id['air']
        self.material[:, ws:we] = self.lib.material_to_id['concrete']
        self.material[:, we:] = self.lib.material_to_id['vacuum']
        cy, cx = self.height // 2, re // 2
        self._heat_mask = np.zeros((self.height, self.width), dtype=bool)
        self._heat_mask[cy-3:cy+3, cx-3:cx+3] = True
        self.T[self._heat_mask] = self.heat_source_temp

    def reset(self):
        self.T.fill(0)
        self.material.fill(0)
        self.frame_count = 0
        self._setup_default()

    def step(self, n=1):
        for _ in range(n):
            laplacian = (self.T[2:,1:-1] + self.T[:-2,1:-1] + self.T[1:-1,2:] + self.T[1:-1,:-2] - 4*self.T[1:-1,1:-1]) / (self.dx**2)
            a = np.take(self.alpha, self.material[1:-1,1:-1])
            self.T[1:-1,1:-1] += a * self.dt * laplacian
            self.T[:, 0] = self.left_temp
            self.T[:, -1] = self.env.get_external_temperature(self.frame_count)
            self.T[0, :] = self.T[1, :]
            self.T[-1, :] = self.T[-2, :]
            if self._heat_mask is not None:
                self.T[self._heat_mask] = self.heat_source_temp
            self.frame_count += 1

    def design_wall(self, layers):
        re = int(self.width * 0.2)
        ws, we = re, int(self.width * 0.7)
        self.material[:, ws:we] = self.lib.material_to_id['air']
        if layers:
            lw = (we - ws) // len(layers)
            for i, name in enumerate(layers):
                if name in self.lib.material_to_id:
                    self.material[:, ws+i*lw:min(ws+(i+1)*lw, we)] = self.lib.material_to_id[name]

    def add_defect(self, dtype, y, x, h=5, w=10):
        mid = {'thermal_bridge': 'copper', 'crack': 'air'}.get(dtype)
        if mid and mid in self.lib.material_to_id:
            self.material[y:y+h, x:x+w] = self.lib.material_to_id[mid]

    def metrics(self):
        re = int(self.width * 0.2)
        we = int(self.width * 0.7)
        room = self.T[:, :re]
        wall = self.T[:, re:we]

        cost = 0.0
        weight = 0.0
        for i in range(len(self.lib.materials)):
            n = np.sum(self.material == i)
            cost += n * float(self.cost_vals[i]) / 1000
            weight += n * float(self.density_vals[i]) / 1000

        wT = self.T[:, re:we]
        dTdx = np.diff(wT, axis=1) / self.dx
        kw = np.take(self.k_vals, self.material[:, re:we])
        q = float(np.mean(-kw[:, :-1] * dTdx))
        dT = float(np.mean(self.T[:, re]) - np.mean(self.T[:, we - 1]))
        Rv = dT / (abs(q) + 1e-10)

        return {
            'room_avg': float(np.mean(room)),
            'room_std': float(np.std(room)),
            'wall_avg': float(np.mean(wall)),
            'wall_max': float(np.max(wall)),
            'wall_min': float(np.min(wall)),
            'heat_flux': q,
            'delta_T': dT,
            'R_value': Rv,
            'cost': cost,
            'weight': weight,
            'total_energy': float(np.sum(self.T)),
            'frame': self.frame_count,
        }

    def state(self):
        return {
            'T': self.T.tolist(),
            'material': self.material.tolist(),
            'profile': self.T[self.height // 2, :].tolist(),
            'metrics': self.metrics(),
            'materials': [{'key': k, 'name': v['name'], 'alpha': v['alpha'],
                           'k': v['k'], 'density': v['density'], 'cost': v['cost'],
                           'color': v['color']} for k, v in self.lib.materials.items()],
        }


# ─── Flask App ──────────────────────────────────────────────

app = Flask(__name__)
sim = ThermalSim(w=80, h=50)
sim.design_wall(['ceramic', 'aerogel', 'metal_insulation', 'concrete'])

# 对比模式用的第二个仿真
sim2 = None
# 故事模式状态
story_active = False
story_scene = 0
story_frame = 0
story_scenes = [
    {'name':'场景1: 火星环境','layers':[],'frames':200},
    {'name':'场景2: 无保温·纯混凝土','layers':['concrete','concrete','concrete'],'frames':300},
    {'name':'场景3: 基础保温·混凝土+泡沫+混凝土','layers':['concrete','foam','concrete'],'frames':300},
    {'name':'场景4: 优化设计·多层高性能材料','layers':['ceramic','aerogel','metal_insulation','concrete'],'frames':400},
    {'name':'场景5: 隐患·热桥缺陷','layers':['ceramic','aerogel','metal_insulation','concrete'],'frames':300},
]


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/state')
def api_state():
    return jsonify(sim.state())


@app.route('/api/step', methods=['POST'])
def api_step():
    n = request.json.get('n', 5) if request.is_json else 5
    sim.step(n)
    return jsonify(sim.state())


@app.route('/api/design', methods=['POST'])
def api_design():
    data = request.json
    sim.design_wall(data.get('layers', []))
    return jsonify(sim.state())


@app.route('/api/defect', methods=['POST'])
def api_defect():
    data = request.json
    sim.add_defect(data['type'], data.get('y', 20), data.get('x', 25),
                   data.get('h', 5), data.get('w', 10))
    return jsonify(sim.state())


@app.route('/api/preset', methods=['POST'])
def api_preset():
    data = request.json
    name = data.get('name', '')
    presets = {
        'basic': ['concrete', 'concrete', 'concrete'],
        'advanced': ['concrete', 'foam', 'concrete'],
        'optimized': ['ceramic', 'aerogel', 'metal_insulation', 'concrete'],
    }
    layers = presets.get(name, ['concrete', 'concrete', 'concrete'])
    sim.design_wall(layers)
    return jsonify(sim.state())


@app.route('/api/params', methods=['POST'])
def api_params():
    data = request.json
    if 'room_temp' in data:
        sim.left_temp = float(data['room_temp'])
    if 'mars_min' in data and 'mars_max' in data:
        sim.env.set_temperature_range(data['mars_min'], data['mars_max'])
    return jsonify({'ok': True})


@app.route('/api/reset', methods=['POST'])
def api_reset():
    global story_active, story_scene, story_frame
    sim.reset()
    story_active = False
    story_scene = 0
    story_frame = 0
    sim.design_wall(['ceramic', 'aerogel', 'metal_insulation', 'concrete'])
    return jsonify(sim.state())


@app.route('/api/story/start', methods=['POST'])
def api_story_start():
    global story_active, story_scene, story_frame, sim2
    story_active = True
    story_scene = 0
    story_frame = 0
    sim.reset()
    # 应用第一个场景
    s = story_scenes[0]
    sim.design_wall(s['layers'])
    sim2 = None
    return jsonify({'scene': story_scene, 'name': s['name'], 'total': len(story_scenes),
                    'scene_frames': s['frames'], **sim.state()})


@app.route('/api/story/next', methods=['POST'])
def api_story_next():
    global story_active, story_scene, story_frame
    if not story_active:
        return jsonify({'done': True})
    story_frame += 5
    sim.step(5)
    s = story_scenes[story_scene]
    if story_frame >= s['frames']:
        story_scene += 1
        story_frame = 0
        if story_scene >= len(story_scenes):
            story_active = False
            return jsonify({'done': True, **sim.state()})
        s = story_scenes[story_scene]
        sim.reset()
        sim.design_wall(s['layers'])
        if story_scene == 4:  # 热桥场景
            sim.add_defect('thermal_bridge', sim.height // 2 - 4, int(sim.width * 0.3), 8, 20)
    return jsonify({'scene': story_scene, 'name': s['name'], 'total': len(story_scenes),
                    'scene_frame': story_frame, 'scene_frames': s['frames'],
                    'done': False, **sim.state()})


@app.route('/api/compare/start', methods=['POST'])
def api_compare_start():
    global sim2
    sim2 = ThermalSim(w=80, h=50)
    sim2.design_wall(['concrete', 'foam', 'concrete'])
    sim.reset()
    sim.design_wall(['ceramic', 'aerogel', 'metal_insulation', 'concrete'])
    return jsonify({'a': sim.state(), 'b': sim2.state()})


@app.route('/api/compare/step', methods=['POST'])
def api_compare_step():
    global sim2
    n = request.json.get('n', 5) if request.is_json else 5
    sim.step(n)
    if sim2:
        sim2.step(n)
    return jsonify({'a': sim.state(), 'b': sim2.state() if sim2 else None})


if __name__ == '__main__':
    print("=" * 50)
    print("火星基地隔热墙优化 — Web 热设计工作室")
    print("浏览器打开: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, host='0.0.0.0', port=5000)
