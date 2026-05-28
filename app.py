import streamlit as st
import pandas as pd
from datetime import datetime, date
import pytz
import os

# --- 页面全局配置 ---
st.set_page_config(page_title="实时智能课表", page_icon="🏫", layout="wide")

# --- 1. 核心时间推算模块 ---
# 设定时区
tz = pytz.timezone('Asia/Taipei')
now = datetime.now(tz)

# 根据用户设定的锚点：2026年5月28日 是 第13周 周四
# 推算出第1周的起始日（周一）为 2026年3月2日
TERM_START_DATE = date(2026, 3, 2)

# 计算系统的“真实状态”
days_since_start = (now.date() - TERM_START_DATE).days
real_week = (days_since_start // 7) + 1
real_weekday = now.weekday()  # 0=周一, 6=周日
real_hour = now.hour
real_period = "上午" if real_hour < 12 else "下午"

# 限制真实周次在 1-18 周之间
real_week = max(1, min(real_week, 18))

weekday_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"}


# --- 2. 数据加载模块 ---
@st.cache_data
def load_schedule_data():
    """
    自动读取目录下的 18 个 CSV 文件。
    假设 CSV 包含以下标准列名：['星期', '时段', '时间', '课程', '老师', '教室']
    """
    schedule_dict = {}
    for i in range(1, 19):
        # 匹配你上传的文件名格式
        filename = f"课表.xlsx - 第{i}周.csv"

        if os.path.exists(filename):
            try:
                df = pd.read_csv(filename)
                # 清理可能的空行
                df = df.dropna(how='all')
                schedule_dict[i] = df
            except Exception as e:
                st.error(f"读取第 {i} 周数据时出错: {e}")
                schedule_dict[i] = pd.DataFrame()
        else:
            # 如果文件不存在，初始化为空表格以防报错
            schedule_dict[i] = pd.DataFrame()

    return schedule_dict


# 执行数据加载
all_weeks_data = load_schedule_data()

# --- 3. 侧边栏交互控制 ---
st.sidebar.title("⚙️ 课表控制台")

# 默认选中当前的“真实周次”和“真实星期”
selected_week = st.sidebar.selectbox(
    "切换周次",
    options=list(range(1, 19)),
    index=real_week - 1,
    format_func=lambda x: f"第 {x} 周"
)

selected_weekday_name = st.sidebar.selectbox(
    "切换星期",
    options=list(weekday_map.values()),
    index=real_weekday
)

# 反查选中的星期对应的数字索引 (0-6)
selected_weekday_idx = [k for k, v in weekday_map.items() if v == selected_weekday_name][0]

# --- 4. 主界面视图渲染 ---
st.title("🏫 智能实时课表系统")

# 状态指示牌
is_current_day = (selected_week == real_week) and (selected_weekday_idx == real_weekday)

if is_current_day:
    st.success(
        f"🟢 **实时状态追踪中**：当前是 **第{real_week}周 {weekday_map[real_weekday]} {real_period}** (时间: {now.strftime('%H:%M')})")
else:
    st.info(
        f"⚪ **浏览模式**：正在查看 **第{selected_week}周 {selected_weekday_name}** 的课表（当前实际为第{real_week}周）")

st.divider()

# 获取选定周次的数据
current_week_df = all_weeks_data.get(selected_week, pd.DataFrame())

# 数据清洗与筛选机制
if not current_week_df.empty:
    # 确保列名包含我们需要的基础字段（做容错处理）
    expected_cols = ['星期', '时段', '时间', '课程', '老师', '教室']
    available_cols = [col for col in expected_cols if col in current_week_df.columns]

    # 筛选出选定“星期”的数据
    if '星期' in current_week_df.columns:
        day_df = current_week_df[current_week_df['星期'] == selected_weekday_name]
    else:
        day_df = pd.DataFrame()  # 如果格式不对，显示为空
else:
    day_df = pd.DataFrame()

# 渲染上下午模块
col1, col2 = st.columns(2)

with col1:
    st.subheader("☀️ 上午时段")
    if not day_df.empty and '时段' in day_df.columns:
        morning_df = day_df[day_df['时段'] == '上午'].drop(columns=['星期', '时段'], errors='ignore')
    else:
        morning_df = pd.DataFrame()

    if not morning_df.empty:
        # 如果是当前的真实时间段，使用边框高亮或特殊提示
        if is_current_day and real_period == "上午":
            st.markdown("🔥 **正在进行中**")
        st.dataframe(morning_df, use_container_width=True, hide_index=True)
    else:
        st.write("🍵 上午无课")

with col2:
    st.subheader("🌙 下午时段")
    if not day_df.empty and '时段' in day_df.columns:
        afternoon_df = day_df[day_df['时段'] == '下午'].drop(columns=['星期', '时段'], errors='ignore')
    else:
        afternoon_df = pd.DataFrame()

    if not afternoon_df.empty:
        if is_current_day and real_period == "下午":
            st.markdown("🔥 **正在进行中**")
        st.dataframe(afternoon_df, use_container_width=True, hide_index=True)
    else:
        st.write("🍵 下午无课")

# --- 数据格式说明 ---
with st.expander("⚠️ 数据源格式要求 (点击查看)"):
    st.write("""
    代码目前假设你上传的 CSV 文件（如 `课表.xlsx - 第一周.csv`）是**清单（扁平化）结构**。
    必须包含以下列名（表头）：`星期`, `时段`, `时间`, `课程`, `老师`, `教室`。

    *示例：*
    | 星期 | 时段 | 时间 | 课程 | 老师 | 教室 |
    | :--- | :--- | :--- | :--- | :--- | :--- |
    | 星期四 | 上午 | 08:00-09:40 | 高等数学 | 张三 | 教A-101 |
    | 星期四 | 下午 | 14:00-15:40 | 大学物理 | 李四 | 教B-202 |

    如果你的 CSV 是类似 Excel 原生的“网格结构”（比如上面是星期一到日，左边是节次），你需要先将其转为上述清单结构，或者使用 Pandas 的 `melt` 函数对数据加载模块进行清洗重组。
    """)