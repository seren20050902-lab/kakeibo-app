import streamlit as st
import google.generativeai as genai
import json
import pandas as pd
import os
from datetime import date
from dotenv import load_dotenv

# API設定
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# モデル取得関数
def get_model():
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods and 'flash' in m.name:
            return genai.GenerativeModel(m.name)
    return None

# データ読み込み・初期化関数
def load_data():
    if os.path.exists('kakeibo_data.csv'):
        df = pd.read_csv('kakeibo_data.csv')
        # 必要なカラムがなければ補完
        if 'date' not in df.columns: df['date'] = str(date.today())
        if 'status' not in df.columns: df['status'] = '在庫あり'
        return df
    else:
        return pd.DataFrame(columns=["date", "item", "price", "category", "status"])

# JSON抽出用ヘルパー
def extract_json(res_text):
    start = res_text.find('[')
    end = res_text.rfind(']') + 1
    data = json.loads(res_text[start:end])
    df_new = pd.DataFrame(data)
    df_new['date'] = str(date.today())
    df_new['status'] = '在庫あり'
    return df_new

# アプリ設定
st.set_page_config(page_title="家計簿＆在庫管理", layout="wide")
st.title("🛒 家計簿＆在庫管理アプリ")

if 'df' not in st.session_state:
    st.session_state['df'] = load_data()

# タブの構成
tab1, tab2, tab3, tab4 = st.tabs(["📄 入力(レシート/手動)", "🎙️ 音声入力", "📋 一覧と分析", "📦 在庫と予測"])

# 1. 入力タブ
with tab1:
    st.subheader("記録方法を選択")
    input_mode = st.radio("記録方法", ["レシート画像から解析", "手動で入力"])
    
    if input_mode == "レシート画像から解析":
        uploaded_file = st.file_uploader("レシート画像をアップロード", type=["jpg", "png", "jpeg"])
        if uploaded_file and st.button("画像から解析"):
            model = get_model()
            with st.spinner("解析中..."):
                res = model.generate_content(["レシートから品名、金額、カテゴリを抽出しJSONで返して。[{\"item\": \"品名\", \"price\": 金額, \"category\": \"分類\"}]", {"mime_type": "image/jpeg", "data": uploaded_file.getvalue()}])
                st.session_state['df'] = pd.concat([st.session_state['df'], extract_json(res.text)], ignore_index=True)
                st.rerun()
    else:
        with st.form("manual_input_form"):
            item_name = st.text_input("品名を入力")
            price = st.number_input("金額を入力", min_value=0)
            if st.form_submit_button("AIで分類して追加"):
                with st.spinner("AIが分類中..."):
                    model = get_model()
                    prompt = f"品名: {item_name}。この品物を、次のカテゴリから1つだけ選んで分類してください：['食費', '日用品', '趣味・娯楽', '交際費', 'その他']。カテゴリ名のみを出力してください。"
                    ai_category = model.generate_content(prompt).text.strip()
                    if ai_category not in ['食費', '日用品', '趣味・娯楽', '交際費', 'その他']: ai_category = 'その他'
                    
                    new_row = pd.DataFrame([{"date": str(date.today()), "item": item_name, "price": price, "category": ai_category, "status": "在庫あり"}])
                    st.session_state['df'] = pd.concat([st.session_state['df'], new_row], ignore_index=True)
                    st.rerun()

# 2. 音声入力
with tab2:
    audio_value = st.audio_input("音声で商品を追加")
    if audio_value:
        model = get_model()
        with st.spinner("解析中..."):
            res = model.generate_content(["音声から品名、金額、カテゴリを抽出してJSONで返して。[{\"item\": \"品名\", \"price\": 金額, \"category\": \"分類\"}]", {"mime_type": "audio/wav", "data": audio_value.getvalue()}])
            st.session_state['df'] = pd.concat([st.session_state['df'], extract_json(res.text)], ignore_index=True)
            st.rerun()

# 3. 一覧と分析
with tab3:
    st.subheader("全データ一覧と分析")
    
    # 初期化ボタン
    if st.button("⚠️ 全データを削除して初期化"):
        st.session_state['df'] = pd.DataFrame(columns=["date", "item", "price", "category", "status"])
        st.session_state['df'].to_csv('kakeibo_data.csv', index=False)
        st.rerun()

    if not st.session_state['df'].empty:
        col1, col2 = st.columns(2)
        with col1:
            st.write("### 日別の出費推移")
            st.bar_chart(st.session_state['df'].groupby('date')['price'].sum())
        with col2:
            st.write("### カテゴリ別の出費")
            st.bar_chart(st.session_state['df'].groupby('category')['price'].sum())

    edited_df = st.data_editor(st.session_state['df'], num_rows="dynamic", use_container_width=True)
    if not edited_df.equals(st.session_state['df']):
        st.session_state['df'] = edited_df
        st.session_state['df'].to_csv('kakeibo_data.csv', index=False)
        st.rerun()

# 4. 在庫と予測
with tab4:
    st.subheader("現在の在庫一覧")
    st.dataframe(st.session_state['df'][st.session_state['df']['status'] == '在庫あり'], use_container_width=True)
    if st.button("AIに相談する"):
        with st.spinner("分析中..."):
            model = get_model()
            res = model.generate_content(f"以下の買い物履歴を分析し、消費ペースを考慮して次に買うべきものを予測してアドバイスして。\n{st.session_state['df'].to_csv(index=False)}")
            st.write(res.text)