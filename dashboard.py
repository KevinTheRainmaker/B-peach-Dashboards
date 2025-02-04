import streamlit as st
import pandas as pd
import requests
import base64
import matplotlib.pyplot as plt
import seaborn as sns
from io import StringIO
import os 

st.set_page_config(layout="wide")

# GitHub API 기본 설정
GITHUB_API_URL = "https://api.github.com/repos"
OWNER = "KevinTheRainmaker"  # 깃허브 사용자명
REPO = "B-Peach-Evaluation"  # 레포지토리 이름
FOLDER_PATH = "results"  # 폴더 경로

if "GITHUB_ACTIONS" not in os.environ:
    from dotenv import load_dotenv
    print('Checking for Streamlit secrets...')
    
    # Streamlit 환경에서 secrets가 있는 경우
    if "ACCESS_TOKEN" in st.secrets:
        print('Loading API Key from Streamlit Secrets...')
        ACCESS_TOKEN = st.secrets["ACCESS_TOKEN"]
    else:
        print('Loading API Key from local .env file...')
        load_dotenv()
        ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
else:
    print('Loading API Key from GitHub Secrets...')
    ACCESS_TOKEN = os.getenv("ACCESS_TOKEN", st.secrets.get("ACCESS_TOKEN"))

# Get the list of files in the GitHub folder
def get_file_list():
    headers = {"Authorization": f"token {ACCESS_TOKEN}"}
    url = f"{GITHUB_API_URL}/{OWNER}/{REPO}/contents/{FOLDER_PATH}"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        files = response.json()
        return [file['name'] for file in files if file['name'].endswith('.csv')]
    else:
        st.error("❌ Failed to fetch files from GitHub.")
        return []

# Fetch the content of a specific CSV file
@st.cache_data
def fetch_csv_content(file_name):
    headers = {"Authorization": f"token {ACCESS_TOKEN}"}
    url = f"{GITHUB_API_URL}/{OWNER}/{REPO}/contents/{FOLDER_PATH}/{file_name}"
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        file_content = response.json()['content']
        decoded_content = StringIO(base64.b64decode(file_content).decode('utf-8'))
        return pd.read_csv(decoded_content)
    else:
        st.error(f"❌ Failed to fetch the file: {file_name}")
        return pd.DataFrame()

def analysis_pattern(df, weight_factor=2.0):
    # 태그별 번안 방지율 분석
    df['tagged_words'] = df['tagged_words'].apply(eval)

    tag_counts = {}
    tag_em_scores = {}

    for _, row in df.iterrows():
        tags = row['tagged_words']
        em_score = row['em_score']
        
        for tag in tags:
            if tag not in tag_counts:
                tag_counts[tag] = 0
                tag_em_scores[tag] = []
            tag_counts[tag] += 1
            tag_em_scores[tag].append(em_score)

    tag_em_avg = {tag: sum(scores) / len(scores) for tag, scores in tag_em_scores.items()}

    tag_analysis_df = pd.DataFrame({
        'tag': tag_em_avg.keys(),
        'average_em_score': tag_em_avg.values(),
        'tag_count': [tag_counts[tag] for tag in tag_em_avg.keys()]
    }).sort_values(by=lambda df: df["average_em_score"] + (df["tag_count"] * weight_factor), ascending=False, ignore_index=True)
    return tag_analysis_df

# def get_csv_download_link(df, file_name):
#     csv = df.to_csv(index=False, encoding='utf-8-sig')
#     b64 = base64.b64encode(csv.encode()).decode()  # Base64 인코딩
#     href = f'<a href="data:file/csv;base64,{b64}" download="{file_name}">📥 Download {file_name}</a>'
#     return href

# Aggregate all CSV files into one DataFrame
def aggregate_csv_files(file_names):
    all_data = []
    for file_name in file_names:
        df = fetch_csv_content(file_name)
        if not df.empty:
            df['span_count'] = df['original_passage'].str.count(r'<span')  # Calculate <span> tag count
            all_data.append(df)
    return pd.concat(all_data, ignore_index=True) if all_data else pd.DataFrame()

# Streamlit UI
st.title("🍑 B-Peach EM Score Dashboard")

files = get_file_list()
if files:
    st.sidebar.write(f"📂 Found {len(files)} CSV files in the folder.")
    
    # Use session state to store selected file
    if "selected_file" not in st.session_state:
        st.session_state.selected_file = files[0]  # Default to first file

    selected_file = st.sidebar.selectbox(
        "Select a file to preview",
        files,
        index=files.index(st.session_state.selected_file),
        key="selected_file"
    )

    # Aggregate all data
    with st.spinner("📊 Aggregating all CSV data..."):
        aggregated_data = aggregate_csv_files(files)

    if not aggregated_data.empty:
        col1, col2 = st.columns([1.3,0.7])

        with col1:
            st.subheader("📋 Data Overview")
            st.dataframe(aggregated_data, height=400)

        with col2:
            st.subheader("🏸 Pattern Analysis")
            st.dataframe(analysis_pattern(aggregated_data), height=400)

        # Load the selected file separately for statistics
        with st.spinner(f"📄 Loading {selected_file} statistics..."):
            selected_data = fetch_csv_content(selected_file)
            if not selected_data.empty:
                selected_data['span_count'] = selected_data['original_passage'].str.count(r'<span')

                # Display statistics for the selected file
                name = str(selected_file).replace('output_','')
                st.sidebar.subheader(f"📊 Statistics for {name}")
                st.sidebar.write(selected_data.describe())
                
                # CSV 다운로드 버튼 추가
                csv = selected_data.to_csv(index=False, encoding='utf-8-sig')
                st.sidebar.download_button(
                    label="📥 Download CSV",
                    data=csv,
                    file_name=selected_file,
                    mime="text/csv",
                )
            else:
                st.sidebar.write('🤯 Selected data is empty')
        
        # Visualize with a boxplot
        st.subheader("📈 Boxplot of EM Score by Number of <span> Tags")
        plt.figure(figsize=(10, 5))
        sns.boxplot(x='span_count', y='em_score', data=aggregated_data, palette="coolwarm")
        plt.title('Distribution of EM Scores by Number of <span> Tags', fontsize=16, fontweight='bold')
        plt.xlabel('Number of <span> Tags', fontsize=12)
        plt.ylabel('EM Score', fontsize=12)
        plt.grid(axis='y', linestyle='--', alpha=0.7)
        st.pyplot(plt)
    else:
        st.warning("⚠️ No data to visualize.")
else:
    st.warning("⚠️ No CSV files found in the specified folder.")
