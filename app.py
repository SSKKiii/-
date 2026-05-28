import streamlit as st
import pandas as pd
from datetime import datetime, date
import pytz
import os

# --- 页面全局配置 ---
st.set_page_config(page_title="实时智能课表", page_icon="🏫", layout="wide")

# --- 1. 核心时间与映射逻辑 ---
tz = pytz.timezone('Asia/Taipei')
now = datetime.now(tz)

TERM_START_DATE = date(2026, 3, 2)
days_since_start = (now.date() - TERM_START_DATE).days
real_week = (days_since_start // 7) + 1
real_weekday = now.weekday()  # 0=周一, 6=周日
real_hour = now.hour
real_period = "上午" if real_hour < 12 else "下午"
real_week = max(1, min(real_week, 18))

weekday_map = {0: "星期一", 1: "星期二", 2: "星期三", 3: "星期四", 4: "星期五", 5: "星期六", 6: "星期日"}
weekday_short = {0: "周一", 1: "周二", 2: "周三", 3: "周四", 4: "周五", 5: "周六", 6: "周日"}

chinese_nums = {
    1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六', 7: '七', 8: '八', 9: '九', 
    10: '十', 11: '十一', 12: '十二', 13: '十三', 14: '十四', 15: '十五', 16: '十六', 17: '十七', 18: '十八'
}

time_mapping = {
    "1-2": {"时段": "上午", "时间": "08:00-09:40"},
    "3-4": {"时段": "上午", "时间": "10:10-11:50"},
    "5-6": {"时段": "下午", "时间": "14:00-15:40"},
    "7-8": {"时段": "下午", "时间": "16:00-17:40"},
    "9-10": {"时段": "下午", "时间": "19:00-20:30"}
}

# --- 2. [重写] 基于物理矩阵的硬核坐标解析引擎 ---
@st.cache_data
def load_and_parse_csvs():
    parsed_schedule = {}
    debug_info = {"files_found": [], "parsing_errors": {}}
    
    for i in range(1, 19):
        possible_names = [
            f"课表.xlsx - 第{chinese_nums[i]}周.csv",
            f"课表.xlsx - 第{chinese_nums[i]}周 .csv",
            f"课表-第{i}周.xlsx - Sheet1.csv"
        ]
        
        filename = None
        for name in possible_names:
            if os.path.exists(name):
                filename = name
                break
                
        if not filename:
            parsed_schedule[i] = pd.DataFrame()
            continue
            
        debug_info["files_found"].append(filename)
        
        raw_df = None
        for enc in ['utf-8', 'gbk', 'gb18030', 'utf-8-sig']:
            try:
                # 强行读取整个物理矩阵，无视任何表头规范
                raw_df = pd.read_csv(filename, header=None, encoding=enc)
                break 
            except Exception:
                continue
                
        if raw_df is None or raw_df.empty:
            parsed_schedule[i] = pd.DataFrame()
            continue

        try:
            # 1. 精确定位真正的表头所在行 (Y轴)
            header_row_idx = -1
            for idx, row in raw_df.iterrows():
                row_str = "".join([str(x) for x in row.values if pd.notna(x)])
                if ("周一" in row_str or "星期一" in row_str) and ("周二" in row_str or "星期二" in row_str):
                    header_row_idx = idx
                    break
            
            if header_row_idx == -1:
                debug_info["parsing_errors"][i] = "未找到合法的星期表头"
                parsed_schedule[i] = pd.DataFrame()
                continue
                
            header_row = raw_df.iloc[header_row_idx].fillna("")

            # 2. 锁定每一天的精确物理列坐标 (X轴)
            col_indices = {}
            for col_idx, col_name in enumerate(header_row):
                col_str = str(col_name).strip()
                for weekday_idx, weekday_name in weekday_map.items():
                    short_name = weekday_short[weekday_idx]
                    if weekday_name in col_str or short_name in col_str or (len(col_str) == 1 and col_str == weekday_name[-1]):
                        col_indices[weekday_idx] = col_idx
                        break

            # 3. 逐行扫描 X/Y 交叉坐标系提取数据
            flat_rows = []
            for row_idx in range(header_row_idx + 1, len(raw_df)):
                # 时间节次永远在第 0 列
                time_label = str(raw_df.iloc[row_idx, 0]).strip()
                if not time_label or time_label in ["nan", "None", "-"]:
                    continue
                    
                matched_key = None
                for key in time_mapping.keys():
                    if key in time_label or key.replace("-", "~") in time_label:
                        matched_key = key
                        break
                        
                if matched_key:
                    period = time_mapping[matched_key]["时段"]
                    exact_time = time_mapping[matched_key]["时间"]
                else:
                    if any(char in time_label for char in ["1", "2", "3", "4", "上午"]) or (row_idx - header_row_idx) < 3:
                        period = "上午"
                    else:
                        period = "下午"
                    matched_key = time_label
                    exact_time = "时段参考: " + time_label

                # 去特定列(周几)抓取数据
                for weekday_idx, col_idx in col_indices.items():
                    cell_value = raw_df.iloc[row_idx, col_idx]
                    
                    if pd.isna(cell_value) or str(cell_value).strip() in ["", "nan", "无", "-", "None"]:
                        continue
                        
                    # 终极换行符暴力破解：把所有可能导致连字的奇怪符号全部转为真实换行
                    cleaned_val = str(cell_value).replace('\\n', '\n').replace('\r', '\n')
                    lines = [line.strip() for line in cleaned_val.split('\n') if line.strip()]
                    
                    if not lines:
                        continue
                        
                    if len(lines) == 1:
                        course, room, remarks = lines[0], "-", "-"
                    elif len(lines) == 2:
                        course, room, remarks = lines[0], lines[1], "-"
                    else:
                        course, room, remarks = lines[0], lines[1], lines[2]
                        
                    flat_rows.append({
                        "星期": weekday_map[weekday_idx],
                        "时段": period,
                        "节次": matched_key,
                        "具体时间": exact_time,
                        "课程": course,
                        "教室": room,
                        "周次/备注": remarks
                    })
                    
            parsed_schedule[i] = pd.DataFrame(flat_rows)
            
        except Exception as e:
            debug_info["parsing_errors"][i] = f"严重错误: {str(e)}"
            parsed_schedule[i] = pd.DataFrame()
            
    return parsed_schedule, debug_info

# 执行加载
all_weeks_data, debug_log = load_and_parse_csvs()

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
st.title("🏫 郑州大学2026学年春季学期实时课表")

is_current_day = (selected_week == real_week) and (selected_weekday_idx == real_weekday)

if is_current_day:
    st.success(f"🟢 **实时状态追踪中**：当前是 **第{real_week}周 {weekday_map[real_weekday]}** (系统时间: {now.strftime('%H:%M')})")
else:
    st.info(f"⚪ **浏览模式**：正在查看 **第{selected_week}周 {selected_weekday_name}** 的课表（当前实际为第{real_week}周）")

st.divider()

current_week_df = all_weeks_data.get(selected_week, pd.DataFrame())
day_df = current_week_df[current_week_df['星期'] == selected_weekday_name] if not current_week_df.empty else pd.DataFrame()

# ================= 视图区 =================
# 上午视图
st.subheader("☀️ 上午时段")
morning_df = day_df[day_df['时段'] == '上午'].drop(columns=['星期', '时段'], errors='ignore') if not day_df.empty else pd.DataFrame()

if not morning_df.empty:
    if is_current_day and real_period == "上午":
        st.markdown("🔥 **当前进行中**")
    st.dataframe(morning_df, use_container_width=True, hide_index=True)
else:
    st.write("🍵 上午无课")

st.write("")

# 下午视图
st.subheader("🌙 下午与晚间时段")
afternoon_df = day_df[day_df['时段'] == '下午'].drop(columns=['星期', '时段'], errors='ignore') if not day_df.empty else pd.DataFrame()

if not afternoon_df.empty:
    if is_current_day and real_period == "下午":
        st.markdown("🔥 **当前进行中**")
    st.dataframe(afternoon_df, use_container_width=True, hide_index=True)
else:
    st.write("🍵 下午无课")

# --- 5. 错误预警与诊断 ---
if day_df.empty:
    st.error("🚨 注意：当前所选日期没有读取到任何课程！这可能是当天确实没课，或者是文件解析异常。如果是后者，请点开下方诊断工具查看详细原因。")

st.divider()
with st.expander("🛠️ 后台运行日志与错误诊断"):
    st.write(f"✅ **文件探测器**：已成功在仓库中扫描到 {len(debug_log.get('files_found', []))} 个课表文件。")
    if debug_log.get("parsing_errors"):
        st.error("❌ **致命错误抓取**：")
        st.json(debug_log["parsing_errors"])
    else:
        st.success("🟢 内部矩阵引擎未发生任何报错。")
