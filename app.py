import streamlit as st
import json
import requests
import time
import matplotlib.pyplot as plt
from datetime import datetime, date, timedelta
from dotenv import load_dotenv
import os

# 设置页面配置
st.set_page_config(
    page_title="AI饮食助手",
    page_icon="🍎",
    layout="wide"
)

# 设置中文字体（解决matplotlib中文显示问题）
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'WenQuanYi Micro Hei']
plt.rcParams['axes.unicode_minus'] = False

# ---------------------- 安全配置：从环境变量读取密钥 ----------------------

load_dotenv() # 加载.env文件

AGENTS = {
    "recognize": {
        "name": "饮食识别助手",
        "bot_id": os.getenv("RECOG_BOT_ID"),
        "api_url": os.getenv("RECOG_API_URL"),
        "api_token": os.getenv("RECOG_TOKEN")
    },
    "nutrition": {
        "name": "营养计算助手",
        "bot_id": os.getenv("NUTRI_BOT_ID"),
        "api_url": os.getenv("NUTRI_API_URL"),
        "api_token": os.getenv("NUTRI_TOKEN")
    },
    "advice": {
        "name": "健康建议助手",
        "bot_id": os.getenv("ADVICE_BOT_ID"),
        "api_url": os.getenv("ADVICE_API_URL"),
        "api_token": os.getenv("ADVICE_TOKEN")
    }
}
# ---------------------- 核心函数 ----------------------
def call_coze_agent(agent_key, user_input):
    """纯文本调用智能体（极简无报错）"""
    agent = AGENTS[agent_key]
    headers = {
        "Authorization": f"Bearer {agent['api_token']}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    payload = {
        "content": {
            "query": {
                "prompt": [{"type": "text", "content": {"text": user_input}}]
            }
        },
        "type": "query",
        "session_id": f"session_{int(time.time())}",
        "project_id": agent["bot_id"]
    }

    try:
        response = requests.post(agent["api_url"], headers=headers, json=payload, stream=True, timeout=60)
        response.raise_for_status()
        full_answer = ""
        for line in response.iter_lines(decode_unicode=True):
            if line and line.startswith("data:"):
                try:
                    data = json.loads(line[5:].strip())
                    if data.get("type") == "answer":
                        full_answer += data.get("content", {}).get("answer", "")
                except:
                    continue
        return full_answer.strip()
    except Exception as e:
        st.error(f"请求失败：{str(e)}")
        return None

# 数据持久化
def init_session():
    if "meal_records" not in st.session_state:
        st.session_state.meal_records = []

def add_record(meal_type, date_str, foods, nutrition):
    st.session_state.meal_records.append({
        "meal": meal_type, "date": date_str, "foods": foods, "nutrition": nutrition
    })

# 周期统计
def get_records(period):
    today = date.today()
    records = st.session_state.meal_records
    if period == "今日":
        return [r for r in records if r["date"] == today.strftime("%Y-%m-%d")]
    if period == "本周":
        start = today - timedelta(days=today.weekday())
        return [r for r in records if start <= datetime.strptime(r["date"], "%Y-%m-%d").date() <= start+timedelta(6)]
    if period == "本月":
        return [r for r in records if r["date"].startswith(f"{today.year}-{today.month:02d}")]
    if period == "近三个月":
        return [r for r in records if datetime.strptime(r["date"], "%Y-%m-%d").date() >= today-timedelta(90)]
    return records

def total_nutri(records):
    cal, pro, carb, fat = 0,0,0,0
    for r in records:
        n = r["nutrition"]
        cal += n.get("total_calories",0)
        pro += n.get("total_protein",0)
        carb += n.get("total_carbs",0)
        fat += n.get("total_fat",0)
    return cal, pro, carb, fat

# ---------------------- 主界面 ----------------------
def main():
    init_session()
    st.title("🍎 AI智能饮食助手")
    st.subheader("纯文字记录 · 分餐统计 · 长期追踪")

    # 侧边栏
    with st.sidebar:
        st.header("⚙️ 设置")
        goal = st.selectbox("健康目标", ["减脂", "增肌", "维持", "健康饮食"])
        st.markdown("---")
        today_cal = total_nutri(get_records("今日"))[0]
        st.metric("今日热量", f"{today_cal} kcal")

    # 标签页
    tab1, tab2 = st.tabs(["🍽️ 记录饮食", "📈 查看统计"])

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            meal = st.selectbox("选择餐次", ["早餐", "午餐", "晚餐", "加餐"])
        with col2:
            record_date = st.date_input("记录日期", date.today()).strftime("%Y-%m-%d")

        food_desc = st.text_area(
            "📝 描述食物（建议带克数，更精准）",
            placeholder="例：300g银耳莲子粥、100g鸡胸肉、80g米饭",
            height=120
        )

        if st.button("✅ 分析并保存", type="primary", use_container_width=True):
            if not food_desc:
                st.warning("请输入食物描述！")
                return

            with st.spinner("正在分析..."):
                # 1 识别
                foods = call_coze_agent("recognize", food_desc)
                if not foods: return
                try: foods_json = json.loads(foods)
                except: st.error("格式错误"); st.code(foods); return

                # 2 营养
                nutri = call_coze_agent("nutrition", foods)
                if not nutri: return
                try: nutri_json = json.loads(nutri)
                except: st.error("格式错误"); st.code(nutri); return

                # 3 建议
                advice = call_coze_agent("advice", f"目标：{goal}，营养：{nutri}")
                add_record(meal, record_date, foods_json, nutri_json)

            # 展示结果
            st.success("✅ 记录成功！")
            c1,c2,c3 = st.columns(3)
            with c1:
                st.subheader("食物")
                for f in foods_json.get("foods",[]):
                    st.write(f"- {f.get('amount','')}{f.get('unit','')} {f.get('name','')}")
            with c2:
                st.subheader("营养")
                st.metric("热量", f"{nutri_json.get('total_calories',0)} kcal")
                st.metric("蛋白质", f"{nutri_json.get('total_protein',0)}g")
                st.metric("碳水", f"{nutri_json.get('total_carbs',0)}g")
            with c3:
                st.subheader("建议")
                st.write(advice)

    with tab2:
        period = st.selectbox("统计周期", ["今日", "本周", "本月", "近三个月"])
        records = get_records(period)
        cal, pro, carb, fat = total_nutri(records)

        st.subheader(f"{period} 总摄入")
        a,b,c,d = st.columns(4)
        a.metric("总热量", f"{cal} kcal")
        b.metric("蛋白质", f"{pro}g")
        c.metric("碳水", f"{carb}g")
        d.metric("脂肪", f"{fat}g")

        st.subheader("📋 全部记录")
        for r in records:
            with st.expander(f"{r['date']} | {r['meal']}"):
                food_list = [f"{f.get('amount','')}{f.get('unit','')} {f.get('name','')}" for f in r["foods"].get("foods",[])]
                st.write("食物：", "，".join(food_list))
                st.write(f"热量：{r['nutrition'].get('total_calories',0)} kcal")

if __name__ == "__main__":
    main()