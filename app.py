import streamlit as st
import pandas as pd
from datetime import datetime, date
import pytz
import os

# --- 页面全局配置 ---
st.set_page_config(page_title="实时智能课表", page_icon="🏫", layout="wide")

# --- 1. 核心时间推算模块 ---
tz = pytz.timezone('Asia/Shanghai')
now = datetime.now(tz)

# 根据锚点：2026年5月28日 是 第13周 周四，推算第1周周一为 2026年3月2日
TERM_START_DATE = date(2026, 3, 2)
days_since_start = (now.date() - TERM_START_DATE).days
real_week = (days_since_start // 7) + 1
real_weekday = now.weekday()  # 0=周一, 6=周日
real_hour = now.hour
real_period = "上午" if real_hour < 12 else "下午"
real_week = max(1, min(real_week, 18))

weekday_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"}

# --- 2. 矩阵网格数据自动解析模块 ---
@st.cache_data
def load_and_parse_grid_data():
    """
    自动解析矩阵网格课表（列为星期，行为节次，单元格内换行包含课程详情）
    """
    parsed_schedule = {} 
    
    for i in range(1, 19):
        filename = f"课表.xlsx - 第{i}周.csv"
        if not os.path.exists(filename):
            parsed_schedule[i] = pd.DataFrame()
            continue
            
        try:
            # 读取原始二维网格 CSV
            raw_df = pd.read_csv(filename)
            if raw_df.empty:
                parsed_schedule[i] = pd.DataFrame()
                continue
                
            flat_rows = []
            
            # 遍历周一到周日这 7 列
            for weekday_idx, weekday_name in weekday_map.items():
                # 兼容处理：有些导出格式可能没有“星期”两个字，只有“一”、“二”或者“周一”
                actual_col_name = None
                for col in raw_df.columns:
                    if weekday_name in col or weekday_name[2:] in col:
                        actual_col_name = col
                        break
                
                if not actual_col_name:
                    continue
                    
                # 提取该星期的整列数据进行逐行解析
                for row_idx, cell_value in enumerate(raw_df[actual_col_name]):
                    # 获取时间或节次标签（默认第一列）
                    time_label = str(raw_df.iloc[row_idx, 0]).strip()
                    
                    # 过滤空单元格
                    if pd.isna(cell_value) or str(cell_value).strip() in ["", "nan", "无", "-"]:
                        continue
                        
                    # 时段粗略推算逻辑：包含1/2/3/4节或上午字样的归为上午，其余为下午
                    if any(x in time_label for x in ["1", "2", "3", "4", "上午", "08:", "10:"]):
                        period = "上午"
                    else:
                        period = "下午"
                        
                    # 单元格文本按换行符拆分
                    lines = [line.strip() for line in str(cell_value).split('\n') if line.strip()]
                    
                    # 提取具体维度变量
                    course = lines[0] if len(lines) > 0 else "未录入课程"
                    teacher = lines[1] if len(lines) > 1 else "未分配老师"
                    room = lines[2] if len(lines) > 2 else "未指定教室"
                    
                    flat_rows.append({
                        "星期": weekday_name,
                        "时段": period,
                        "时间/节次": time_label,
                        "课程": course,
                        "老师": teacher,
                        "教室": room
                    })
                    
            if flat_rows:
                parsed_schedule[i] = pd.DataFrame(flat_rows)
            else:
                parsed_schedule[i] = pd.DataFrame()
                
        except Exception as e:
            st.error(f"解析第 {i} 周课表矩阵失败: {e}")
            parsed_schedule[i] = pd.DataFrame()
            
    return parsed_schedule

# 执行解析
all_weeks_data = load_and_parse_grid_data()

# --- 3. 侧边栏交互控制 ---
st.sidebar.title("⚙️ 课表控制台")

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

selected_weekday_idx = [k for k, v in weekday_map.items() if v == selected_weekday_name][0]

# --- 4. 主界面视图渲染 ---
st.title("🏫 智能实时课表系统")

is_current_day = (selected_week == real_week) and (selected_weekday_idx == real_weekday)

if is_current_day:
    st.success(f"🟢 **实时状态追踪中**：当前是 **第{real_week}周 {weekday_map[real_weekday]} {real_period}** (时间: {now.strftime('%H:%M')})")
else:
    st.info(f"⚪ **浏览模式**：正在查看 **第{selected_week}周 {selected_weekday_name}** 的课表（当前实际为第{real_week}周）")

st.divider()

current_week_df = all_weeks_data.get(selected_week, pd.DataFrame())

if not current_week_df.empty:
    day_df = current_week_df[current_week_df['星期'] == selected_weekday_name]
else:
    day_df = pd.DataFrame()

col1, col2 = st.columns(2)

with col1:
    st.subheader("☀️ 上午时段")
    if not day_df.empty:
        morning_df = day_df[day_df['时段'] == '上午'].drop(columns=['星期', '时段'], errors='ignore')
    else:
        morning_df = pd.DataFrame()

    if not morning_df.empty:
        if is_current_day and real_period == "上午":
            st.markdown("🔥 **当前时段课程**")
        st.dataframe(morning_df, use_container_width=True, hide_index=True)
    else:
        st.write("🍵 上午无课")

with col2:
    st.subheader("🌙 下午时段")
    if not day_df.empty:
        afternoon_df = day_df[day_df['时段'] == '下午'].drop(columns=['星期', '时段'], errors='ignore')
    else:
        afternoon_df = pd.DataFrame()

    if not afternoon_df.empty:
        if is_current_day and real_period == "下午":
            st.markdown("🔥 **当前时段课程**")
        st.dataframe(afternoon_df, use_container_width=True, hide_index=True)
    else:
        st.write("🍵 下午无课")
