# 导入Streamlit网页交互框架，用于快速搭建移动端/电脑端网页GUI
import streamlit as st
# 导入数学标准库，提供三角函数、开方、幂运算等物理计算能力
import math
# 导入绘图库，用于绘制飞行高度、左右偏移两组弹道轨迹图
import matplotlib.pyplot as plt

# ===================== 移动端视口配置：修复网页无法正常缩放问题 =====================
# 适配手机/平板，允许页面缩放、自动匹配屏幕宽度
st.markdown(
    '<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">',
    unsafe_allow_html=True
)

# ===================== Matplotlib 全局绘图配置（解决中文乱码、负号异常） =====================
# 设置图表默认中文字体，避免中文显示为方框
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Zen Hei", "Heiti TC"]
# 关闭Unicode负号兼容限制，解决坐标轴负号显示异常问题
plt.rcParams["axes.unicode_minus"] = False
# 设置图表全局默认字体大小
plt.rcParams["font.size"] = 10

# ===================== 高尔夫物理全局常量（与桌面版核心参数完全一致） =====================
# 重力加速度，单位：米/平方秒，地球标准物理常量
g = 9.8
# 标准高尔夫球半径，单位：米，职业赛事通用尺寸
ball_r = 0.02133
# 计算高尔夫球横截面积，用于空气阻力、马格努斯升力公式计算
A = math.pi * ball_r ** 2
# 标准高尔夫球质量，单位：千克，职业赛事通用重量
m = 0.04593
# 模拟时间步长，数值越小，弹道轨迹计算精度越高
dt = 0.005
# 长度单位转换系数：米 → 码，高尔夫行业专用单位
METER_TO_YARD = 1.09361
# 侧旋飞行衰减系数，控制球在空中飞行时侧旋的衰减速度
side_spin_decay = 0.995
# 自定义侧旋作用力系数，控制球左右弯曲的幅度
side_con = 3
# 弹道模拟最大循环步数，防止死循环导致程序卡死
MAX_STEPS = 10000
# 单轴速度上限，限制极值，避免高速运算出现数值溢出
MAX_SPEED = 100

# 左右手球员+球路 距离补偿系数
# 右手球员+左曲球：距离增益2.2%
DIST_BONUS_DRAW_RIGHT = 1.022
# 右手球员+右曲球：距离损耗3.3%
DIST_LOSS_FADE_RIGHT = 0.967
# 左手球员+右曲球：距离增益2.2%
DIST_BONUS_FADE_LEFT = 1.022
# 左手球员+左曲球：距离损耗3.3%
DIST_LOSS_DRAW_LEFT = 0.967

# 高低速空气动力学分界参数（区分木杆/铁杆物理特性）
# 低速分界球速：130英里/小时，对应铁杆、挖起杆场景
speed_base_low = 130
# 低速环境空气密度
rho_low = 1.25
# 低速状态空气阻力系数
Cd_low = 0.365
# 低速落地弹性恢复系数，控制落地反弹高度
COR_low = 0.17
# 低速地面摩擦系数，控制落地后滚动距离
mu_low = 0.06
# 低速状态最大升力系数
Cl_max_low = 0.48
# 低速侧旋作用力比例系数
side_scale_low = 0.20

# 高速分界球速：160英里/小时，对应木杆、长杆场景
speed_base_high = 160
# 高速环境空气密度
rho_high = 1.180
# 高速状态空气阻力系数
Cd_high = 0.270
# 高速落地弹性恢复系数
COR_high = 0.18
# 高速地面摩擦系数
mu_high = 0.055
# 高速状态最大升力系数
Cl_max_high = 0.35
# 高速侧旋作用力比例系数
side_scale_high = 0.22

# 高倒旋惩罚机制参数（防止超高倒旋导致弹道物理异常）
# 倒旋阈值：超过6000转/分，触发额外阻力惩罚
backspin_threshold = 6000
# 高倒旋额外阻力系数
drag_penalty_factor = 0.00006
# 高倒旋升力衰减系数，倒旋过高会降低升力效率
lift_efficiency_drop = 0.00006
# 落地回滚临界倒旋值：超过该数值球落地会反向回滚
roll_reversal_spin = 7000
# 落地回滚临界角度：落地角度大于该值才会触发回滚
roll_reversal_angle = 45


# ===================== 单位转换工具函数 =====================
# 速度单位转换：英里/小时 → 米/秒，统一物理计算单位
def mph_to_ms(mph):
    return mph * 0.44704


# 旋转单位转换：转/分钟 → 弧度/秒，旋转物理量标准单位
def rpm_to_rad(rpm):
    return rpm * 2 * math.pi / 60


# 角度单位转换：角度 → 弧度，三角函数计算必须使用弧度制
def deg_to_rad(deg):
    return deg * math.pi / 180


# ===================== 空气动力学参数线性插值函数 =====================
# 根据实时球速，平滑过渡高低速两组空气动力学参数
def get_linear_param(current_speed):
    # 计算高低速分界之间的速度差值
    speed_span = speed_base_high - speed_base_low
    # 计算插值权重，限制在0~1之间，防止参数越界
    scale_ratio = max(0, min(1, (current_speed - speed_base_low) / speed_span))
    # 线性插值计算当前环境空气密度
    rho = rho_low + scale_ratio * (rho_high - rho_low)
    # 线性插值计算当前空气阻力系数
    Cd = Cd_low + scale_ratio * (Cd_high - Cd_low)
    # 线性插值计算当前落地弹性恢复系数
    COR = COR_low + scale_ratio * (COR_high - COR_low)
    # 线性插值计算当前地面摩擦系数
    mu = mu_low + scale_ratio * (mu_high - mu_low)
    # 线性插值计算当前最大升力系数
    Cl_max = Cl_max_low + scale_ratio * (Cl_max_high - Cl_max_low)
    # 线性插值计算当前侧旋作用力系数
    side_scale = side_scale_low + scale_ratio * (side_scale_high - side_scale_low)
    # 返回全套插值后的空气动力学参数
    return rho, Cd, COR, mu, Cl_max, side_scale


# ===================== 核心弹道模拟主函数（飞行+反弹+滚动全流程） =====================
# 入参：杆头速度、球速、发射角、倒旋、侧旋、杆面偏角、左右手球员标识
def golf_simulation(club_head_speed, ball_speed, launch_angle, backspin, sidespin, face_offset, hand_type="right"):
    # 根据当前球速，获取插值后的空气动力学参数
    rho, Cd_base, COR, mu_base, Cl_max_base, side_scale = get_linear_param(ball_speed)
    # 判断杆头速度是否有效（大于0为有效击球）
    valid_head = club_head_speed > 0
    # 计算击球效率（球速/杆头速度），无效则赋值0
    smash = ball_speed / club_head_speed if valid_head else 0
    # 根据侧旋正负判断球路：左曲球/右曲球/直线球
    curve = "左曲球" if sidespin < 0 else "右曲球" if sidespin > 0 else "直线球"
    # 初始化距离修正系数，默认无补偿
    dist_scale = 1.0
    # 根据球员左右手+球路，匹配距离补偿系数
    if hand_type == "right":
        # 右手球员规则：左曲增益、右曲损耗
        if sidespin < 0: dist_scale = DIST_BONUS_DRAW_RIGHT
        if sidespin > 0: dist_scale = DIST_LOSS_FADE_RIGHT
    else:
        # 左手球员规则：右曲增益、左曲损耗
        if sidespin > 0: dist_scale = DIST_BONUS_FADE_LEFT
        if sidespin < 0: dist_scale = DIST_LOSS_DRAW_LEFT

    # 球速单位转换：英里/小时 → 米/秒
    v0 = mph_to_ms(ball_speed)
    # 发射角单位转换：角度 → 弧度
    launch_rad = deg_to_rad(launch_angle)
    # 杆面偏角单位转换：角度 → 弧度
    face_rad = deg_to_rad(face_offset)
    # 计算水平方向总速度
    v_hor_total = v0 * math.cos(launch_rad)
    # 分解X轴初始速度（前进主方向）
    vx = v_hor_total * math.cos(face_rad)
    # 分解Z轴初始速度（左右偏移方向）
    vz = v_hor_total * math.sin(face_rad)
    # 分解Y轴初始速度（垂直高度方向）
    vy = v0 * math.sin(launch_rad)
    # 初始化球的三维坐标，起始位置为原点(0,0,0)
    x, y, z = 0, 0, 0
    # 初始化轨迹存储列表，记录每一步三维坐标
    traj_x, traj_y, traj_z = [0], [0], [0]
    # 初始化实时侧旋数值（飞行过程中会持续衰减）
    cur_side = sidespin
    # 计算超出倒旋阈值的多余倒旋量，用于惩罚计算
    backspin_excess = max(0, backspin - backspin_threshold)
    # 初始化模拟循环步数
    step_count = 0

    # ========== 第一阶段：空中飞行模拟循环（未落地+未超最大步数） ==========
    while step_count < MAX_STEPS and y > -1e-6:
        # 模拟步数自增
        step_count += 1
        # 计算三维合速度
        v_total = math.hypot(vx, vy, vz)
        # 合速度过低，判定球停止运动，退出循环
        if v_total < 0.1: break
        # 计算含高倒旋惩罚的空气阻力系数
        Cd = Cd_base + drag_penalty_factor * backspin_excess if backspin_excess > 0 else Cd_base
        # 限制阻力系数最大值，防止物理异常
        Cd = min(Cd, 0.45)
        # 空气阻力计算公式
        drag = 0.5 * rho * Cd * A * v_total ** 2 / m
        # X轴阻力加速度
        ax = -drag * vx / v_total
        # Y轴阻力加速度
        ay = -drag * vy / v_total
        # Z轴阻力加速度
        az = -drag * vz / v_total

        # 计算含高倒旋惩罚的最大升力系数
        Cl_max = Cl_max_base - lift_efficiency_drop * backspin_excess if backspin_excess > 0 else Cl_max_base
        # 限制升力系数最小值，防止物理异常
        Cl_max = max(Cl_max, 0.2)
        # 倒旋单位转换：转/分钟 → 弧度/秒
        backspin_rad = rpm_to_rad(backspin)
        # 计算旋转比例（球表面线速度 / 飞行合速度）
        spin_ratio = (backspin_rad * ball_r) / v_total if v_total else 0
        # 计算实时升力系数
        Cl = min(0.14 + 0.55 * spin_ratio, Cl_max)
        # 马格努斯升力计算公式
        lift = 0.5 * rho * Cl * A * v_total ** 2 / m
        # 升力叠加到垂直方向加速度
        ay += lift * vx / v_total

        # 侧旋大于阈值时，计算左右偏转力
        if abs(cur_side) > 10:
            # 侧旋随飞行距离逐步衰减
            cur_side *= side_spin_decay ** (dt / 0.1)
            # 侧旋与倒旋的比值，影响偏转力度
            ratio = abs(cur_side) / (abs(backspin) + 1e-6)
            # 侧旋偏转力综合计算公式
            force = lift * ratio * side_scale * side_con
            # 根据侧旋正负，判定左右偏转方向
            if cur_side > 0:
                az += force
            else:
                az -= force

        # 叠加重力加速度（垂直向下）
        ay -= g
        # 更新X轴实时速度
        vx += ax * dt
        # 更新Y轴实时速度
        vy += ay * dt
        # 更新Z轴实时速度
        vz += az * dt
        # 更新X轴实时坐标
        x += vx * dt
        # 更新Y轴实时坐标
        y += vy * dt
        # 更新Z轴实时坐标
        z += vz * dt
        # 记录当前坐标到轨迹列表
        traj_x.append(x)
        traj_y.append(y)
        traj_z.append(z)

    # ========== 第二阶段：落地反弹模拟 ==========
    # 落地后速度按弹性系数衰减，生成反弹初始速度
    vx_b, vy_b, vz_b = vx * COR, abs(vy) * COR, vz * COR
    # 反弹初始坐标（Y轴置0，接触地面）
    x_b, y_b, z_b = x, 0.0, z
    # 重置反弹循环步数
    step_count = 0
    # 反弹循环：限制最大步数+未完全落地
    while step_count < 1000 and y_b > -1e-6:
        step_count += 1
        # 计算反弹阶段合速度
        v_b = math.hypot(vx_b, vy_b, vz_b)
        # 速度过低/数值异常，退出反弹循环
        if v_b < 0.1 or math.isnan(v_b): break
        # 反弹阶段空气阻力计算
        drag_b = 0.5 * rho * Cd * A * v_b ** 2 / m
        # 更新反弹阶段X轴速度
        vx_b -= drag_b * vx_b / v_b * dt
        # 更新反弹阶段Y轴速度（叠加重力+阻力）
        vy_b -= (g + drag_b * vy_b / v_b) * dt
        # 更新反弹阶段Z轴速度
        vz_b -= drag_b * vz_b / v_b * dt
        # 更新反弹X坐标
        x_b += vx_b * dt
        # 更新反弹Y坐标
        y_b += vy_b * dt
        # 更新反弹Z坐标
        z_b += vz_b * dt
        # 记录反弹轨迹
        traj_x.append(x_b)
        traj_y.append(y_b)
        traj_z.append(z_b)

    # ========== 第三阶段：地面滚动模拟 ==========
    # 计算滚动阶段合速度（仅水平方向）
    v_roll = math.hypot(vx_b, vz_b)
    # 初始化滚动阶段坐标
    x_r, z_r = x_b, z_b
    # 赋值地面摩擦系数
    mu = mu_base
    # 重置滚动循环步数
    step_count = 0
    # 滚动循环：速度大于阈值+未超最大步数
    while v_roll > 0.1 and step_count < 1000:
        step_count += 1
        # 数值异常则退出循环
        if math.isnan(vx_b) or math.isnan(vz_b): break
        # 计算滚动减速度（摩擦力产生）
        dec_acc = mu * g
        # 高速滚动时增大摩擦减速度
        if v_roll > 10: dec_acc *= 1.5
        # 更新滚动X轴速度
        vx_b -= dec_acc * (vx_b / v_roll) * dt
        # 更新滚动Z轴速度
        vz_b -= dec_acc * (vz_b / v_roll) * dt
        # 重新计算滚动合速度
        v_roll = math.hypot(vx_b, vz_b)
        # 更新滚动X坐标
        x_r += vx_b * dt
        # 更新滚动Z坐标
        z_r += vz_b * dt

    # ========== 最终结果计算（单位转换+数据封装） ==========
    # 空中落点距离（不含滚动），单位转换+距离补偿
    carry = math.hypot(x, z) * METER_TO_YARD * dist_scale
    # 总距离（空中+落地滚动），单位转换+距离补偿
    total = math.hypot(x_r, z_r) * METER_TO_YARD * dist_scale
    # 最终左右偏移距离，单位转换
    offset = z_r * METER_TO_YARD
    # 计算弹道最高点高度（码）
    max_height = max(traj_y) * METER_TO_YARD

    # 拼接偏移方向描述文本
    offset_str = f"向右偏移{offset:.1f}码" if offset > 0 else f"向左偏移{abs(offset):.1f}码" if offset < 0 else "无偏移"
    # 封装模拟结果字典，新增【击球效率】字段，供前端展示
    result = {
        "总距离": f"{total:.1f}码",
        "落点距离": f"{carry:.1f}码",
        "顶点高度": f"{max_height:.1f}码",
        "偏移": offset_str,
        "球路": curve,
        "击球效率": f"{smash:.3f}"  # 新增击球效率，保留3位小数
    }
    # 返回轨迹坐标列表 + 结果字典
    return traj_x, traj_y, traj_z, result


# ===================== Streamlit 网页界面布局与交互逻辑 =====================
# 网页全局配置：标题、布局模式、网页图标
st.set_page_config(page_title="高尔夫弹道模拟", layout="wide", page_icon="🏌️‍♂️")

# 页面主标题（Markdown格式美化）
st.markdown("""
# 🏌️‍♂️ 高尔夫弹道模拟系统
""", unsafe_allow_html=True)

# 页面分栏：左栏(参数+结果) : 右栏(图表) = 1 : 1.5（适配缩小后的图表）
col1, col2 = st.columns([1, 1.5], gap="large")

# ========== 左侧面板：参数设置 + 模拟结果 ==========
with col1:
    # 左侧子标题
    st.subheader("⚙️ 击球参数设置")
    # 分割线，区分模块
    st.divider()

    # 杆头速度输入框：范围0~200，步长1（加减按钮）
    club_speed = st.number_input("杆头速度 (mph)", min_value=0, max_value=200, value=0, step=1)
    # 球速输入框：范围100~200，步长5（加减按钮）
    ball_speed = st.number_input("球速 (mph)", min_value=100, max_value=200, value=160, step=5)
    # 发射角输入框：范围0~45°，步长1（加减按钮）
    launch = st.number_input("发射角 (°)", min_value=0, max_value=45, value=10, step=1)
    # 倒旋输入框：范围0~10000转，步长100（加减按钮，按需求设置阶梯）
    back = st.number_input("倒旋 (rpm)", min_value=0, max_value=10000, value=2500, step=100)
    # 侧旋输入框：范围-2000~2000转，步长50（已修改为±2000）
    side = st.number_input("侧旋 (rpm)", min_value=-2000, max_value=2000, value=-300, step=50)
    # 杆面偏角输入框：范围-10~10°，步长1（已修改为±10°）
    face = st.number_input("杆面偏角 (°)", min_value=-10, max_value=10, value=2, step=1)

    # 分割线
    st.divider()
    # 模拟触发按钮：主色调、通栏展示
    simulate_btn = st.button("🚀 开始模拟", use_container_width=True, type="primary")

    # 点击模拟按钮后，执行计算并展示结果
    if simulate_btn:
        # 调用核心模拟函数
        tx, ty, tz, res = golf_simulation(club_speed, ball_speed, launch, back, side, face)

        # 结果区域美化布局，三列均分，统一卡片样式
        st.divider()
        st.subheader("📊 模拟结果")
        col_res1, col_res2, col_res3 = st.columns(3)

        # 第一列：总距离、落点距离
        with col_res1:
            st.metric("总距离", res["总距离"], help="球从击球点到最终停止的总距离")
            st.metric("落点距离", res["落点距离"], help="球第一次落地的空中距离")
        # 第二列：顶点高度、击球效率
        with col_res2:
            st.metric("顶点高度", res["顶点高度"], help="弹道最高点的垂直高度")
            st.metric("击球效率", res["击球效率"], help="球速 ÷ 杆头速度，反映击球质量")
        # 第三列：偏移方向、球路类型
        with col_res3:
            st.metric("偏移方向", res["偏移"], help="球最终左右偏移情况")
            st.metric("球路类型", res["球路"], help="球的飞行轨迹类型（左曲/右曲/直线）")

# ========== 右侧面板：弹道轨迹图表展示 ==========
with col2:
    # 图表区域子标题
    st.subheader("📈 弹道轨迹图")
    # 分割线
    st.divider()

    # 仅点击模拟后，才绘制图表
    if simulate_btn and 'tx' in locals():
        # 坐标单位转换：米 → 码（关键修正：z轴取反，解决轨迹左右反向问题）
        x_yd = [p * METER_TO_YARD for p in tx]
        y_yd = [p * METER_TO_YARD for p in ty]
        z_yd = [-p * METER_TO_YARD for p in tz]  # 取反后：杆面正=右出，侧旋负=左曲，完全符合需求

        # 创建画布：2行1列子图，尺寸缩小为(8,6)，和左边栏比例协调
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(8, 6))
        # 自动调整子图间距，防止标题、标签重叠
        fig.tight_layout(pad=3.0)

        # -------- 第一张图：飞行高度轨迹 --------
        # 绘制高度曲线：蓝色、线宽3
        ax1.plot(x_yd, y_yd, color='#1E90FF', linewidth=3, label="飞行高度")
        # 曲线下方半透明填充，美化界面
        ax1.fill_between(x_yd, 0, y_yd, alpha=0.2, color='#1E90FF')
        # 查找轨迹最高点数值、索引、对应水平距离
        high_val = max(y_yd)
        high_idx = y_yd.index(high_val)
        high_x = x_yd[high_idx]
        # 在最高点绘制红色圆点标记，层级置顶不被线条遮挡
        ax1.plot(high_x, high_val, "ro", markersize=8, markeredgecolor='darkred', zorder=5)

        # 设置图表标题、字体大小固定为10
        ax1.set_title("飞行高度轨迹", fontsize=10)
        # X轴标签，字体10号
        ax1.set_xlabel("前进距离（码）", fontsize=10)
        # Y轴标签，字体10号
        ax1.set_ylabel("高度（码）", fontsize=10)
        # 显示网格线，透明度0.3
        ax1.grid(True, alpha=0.3)
        # 图例字体固定为10号
        ax1.legend(fontsize=10)
        # 刻度字体固定为10号
        ax1.tick_params(axis='both', labelsize=10)
        # 固定Y轴下限为0（高度不可能为负）
        ax1.set_ylim(bottom=0)

        # -------- 第二张图：左右偏移轨迹 --------
        # 绘制偏移曲线：橙色、线宽3
        ax2.plot(x_yd, z_yd, color='#FF4500', linewidth=3, label="偏移曲线")
        # 绘制黑色目标中心线（偏移0基准线）
        ax2.axhline(0, color='black', linewidth=1.5, label="目标中心线")

        # 设置图表标题、字体大小固定为10
        ax2.set_title("左右偏移轨迹", fontsize=10)
        # X轴标签，字体10号
        ax2.set_xlabel("前进距离（码）", fontsize=10)
        # Y轴标签，字体10号
        ax2.set_ylabel("偏移距离（码）", fontsize=10)
        # 显示网格线
        ax2.grid(True, alpha=0.3)
        # 图例字体固定为10号
        ax2.legend(fontsize=10)
        # 刻度字体固定为10号
        ax2.tick_params(axis='both', labelsize=10)
        # 固定偏移范围 ±30码，与桌面版保持一致
        ax2.set_ylim(-30, 30)

        # 将Matplotlib图表嵌入Streamlit页面，自适应容器宽度
        st.pyplot(fig, use_container_width=True)
    else:
        # 未点击模拟时，显示友好提示文本
        st.info("👆 请点击「开始模拟」按钮生成弹道轨迹图", icon="ℹ️")