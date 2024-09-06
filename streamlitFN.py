import streamlit as st
import cx_Oracle
from wordcloud import WordCloud
from collections import Counter
from konlpy.tag import Hannanum
import datetime as dt
from datetime import datetime, timedelta
import pandas as pd
import folium
from streamlit_folium import st_folium
import altair as alt
import plotly.express as px
import time
from streamlit_autorefresh import st_autorefresh
import streamlit.components.v1 as components
import os

import cx_Oracle
import os

# Oracle Instant Client 경로 설정
client_lib_dir = os.path.join(os.getcwd(), "instantclient_23_5")
cx_Oracle.init_oracle_client(lib_dir=client_lib_dir)


# 데이터베이스 연결 설정

def get_oracle_connection():
    dsn_tns = cx_Oracle.makedsn(
        os.getenv('DB_HOST', 'localhost'),
        os.getenv('DB_PORT', '1521'),
        sid=os.getenv('DB_SID', 'xe')
    )
    connection = cx_Oracle.connect(
        user=os.getenv('DB_USER', 'base_man'),
        password=os.getenv('DB_PASSWORD', '1111'),
        dsn=dsn_tns
    )
    return connection

# 추천 영상 가져오기
def get_rcmd_videos_from_db(limit=None, offset=None):
    connection = get_oracle_connection()
    cursor = connection.cursor()

    if limit is not None and offset is not None:
        sql = f"""
        SELECT * FROM (
                SELECT a.*, ROWNUM rnum FROM (
            SELECT "제목", "링크", "썸네일", "감성분석", "감성점수"
            FROM EMOTION
            WHERE "감성분석" = '긍정적'
            ORDER BY "추천점수" DESC
            )a
            WHERE ROWNUM <= {offset + limit}
        ) WHERE rnum > {offset}        
    """

    else:
        sql = f"""
                    SELECT "제목", "링크", "썸네일", "감성분석", "감성점수"
                    FROM EMOTION
                    WHERE "감성분석" = '긍정적'
                    ORDER BY "감성점수" DESC
                """



    cursor.execute(sql)
    rows = cursor.fetchall()

    videos = []
    for row in rows:
        videos.append({
            'title': row[0],
            'thumbnail_url': row[2],
            'video_url': row[1],
        })

    cursor.close()
    connection.close()

    return videos

def get_total_emotion_count():
    connection = get_oracle_connection()
    cursor = connection.cursor()

    # 오늘 날짜를 구합니다.


    # 총 비디오 수를 구하는 쿼리
    sql = f"""
        SELECT COUNT(*)
        FROM EMOTION
     
    """

    cursor.execute(sql)
    total_videos = cursor.fetchone()[0]

    cursor.close()
    connection.close()

    return total_videos

# 하이라이트 영상 가져오기
def get_videos_from_db(limit=None, offset=None):
    connection = get_oracle_connection()
    cursor = connection.cursor()

    # 오늘 날짜를 구합니다.
    today_date = datetime.now().date()

    # 페이지네이션을 위한 쿼리
    if limit is not None and offset is not None:
        sql = f"""
            SELECT * FROM (
                SELECT a.*, ROWNUM rnum FROM (
                    SELECT title, thumbnail_url, video_url, upload_date
                    FROM HL_videos
                    WHERE upload_date <= TO_DATE('{today_date}', 'YYYY-MM-DD')
                    ORDER BY upload_date DESC
                ) a
                WHERE ROWNUM <= {offset + limit}
            ) WHERE rnum > {offset}
        """
    else:
        sql = f"""
            SELECT title, thumbnail_url, video_url, upload_date
            FROM HL_videos
            WHERE upload_date <= TO_DATE('{today_date}', 'YYYY-MM-DD')
            ORDER BY upload_date DESC
        """

    cursor.execute(sql)
    rows = cursor.fetchall()

    # 결과를 딕셔너리 형태로 변환
    videos = []
    for row in rows:
        videos.append({
            'title': row[0],
            'thumbnail_url': row[1],
            'video_url': row[2],
            'upload_date': row[3]
        })

    cursor.close()
    connection.close()

    return videos

def get_total_videos_count():
    connection = get_oracle_connection()
    cursor = connection.cursor()

    # 오늘 날짜를 구합니다.
    today_date = datetime.now().date()

    # 총 비디오 수를 구하는 쿼리
    sql = f"""
        SELECT COUNT(*)
        FROM HL_videos
        WHERE upload_date <= TO_DATE('{today_date}', 'YYYY-MM-DD')
    """

    cursor.execute(sql)
    total_videos = cursor.fetchone()[0]

    cursor.close()
    connection.close()

    return total_videos
#경기일정가져오기
def fetch_schedule_with_weather_from_db(date):
    connection = get_oracle_connection()
    cursor = connection.cursor()

    query = """
    SELECT ms.match_time, 
           t1.team_name AS team1_name, 
           t2.team_name AS team2_name, 
           home_team.team_name AS home_team_name, 
           mw.최저기온, 
           mw.최고기온, 
           mw.강우확률, 
           mw.LOCATION
    FROM match_schedule ms
    JOIN team t1 ON ms.team1_code = t1.team_code
    JOIN team t2 ON ms.team2_code = t2.team_code
    JOIN team home_team ON ms.home_team_code = home_team.team_code
    JOIN match_weather mw ON ms.match_id = mw.match_id
    WHERE ms.match_date = TO_DATE(:1, 'YYYY-MM-DD')
    """
    cursor.execute(query, [date])
    rows = cursor.fetchall()

    cursor.close()
    connection.close()

    return rows

# 데이터프레임 생성 함수
def create_schedule_with_weather_df(date):
    rows = fetch_schedule_with_weather_from_db(date)
    data = []

    for row in rows:
        match_time, team1, team2, home_team, low_temp, high_temp, rain_prob, location = row
        home_team_indicator = " 🏠" if team2 == home_team else ""
        data.append({
            "Team 1": team1,
            "Time": match_time,
            "Team 2": team2,
            "Home Indicator": home_team_indicator,
            "Low Temp": low_temp,
            "High Temp": high_temp,
            "Rain Probability": rain_prob,
            "Location": location
        })

    return pd.DataFrame(data)

#랭킹 데이터
def load_rank_data():
    today = dt.datetime.now().strftime('%Y-%m-%d')  # 오늘 날짜를 'YYYY-MM-DD' 형식으로 가져옴
    connection = get_oracle_connection()
    query = f"""
    SELECT rank, team_name, games, wins, draws, losses, win_rate, game_diff
    FROM team_rankings
    WHERE rank_date = TO_DATE('{today}', 'YYYY-MM-DD')
    """
    df = pd.read_sql(query, connection)
    connection.close()

    # 열 이름을 한글로 변경
    df.rename(columns={
        'RANK': '순위',
        'TEAM_NAME': '팀명',
        'GAMES': '경기',
        'WINS': '승',
        'DRAWS': '무',
        'LOSSES': '패',
        'WIN_RATE': '승률',
        'GAME_DIFF': '게임차'
    }, inplace=True)

    return df

def load_all_rank_data():
    connection = get_oracle_connection()
    query = """
    SELECT rank_date, rank, team_name
    FROM team_rankings
    ORDER BY rank_date
    """
    df = pd.read_sql(query, connection)
    connection.close()

    # 열 이름을 한글로 변경
    df.rename(columns={
        'RANK_DATE': '날짜',
        'RANK': '순위',
        'TEAM_NAME': '팀명'
    }, inplace=True)

    # '날짜' 열을 datetime 형식으로 변환하고 날짜만 추출
    df['날짜'] = pd.to_datetime(df['날짜']).dt.date

    return df
#야구장 정보
def get_stadium_data(team_code):
    """
    주어진 팀 코드에 해당하는 구장 데이터를 데이터베이스에서 가져옵니다.
    """
    conn = get_oracle_connection()
    cursor = conn.cursor()

    query = '''
        SELECT 
        stadium_name, 
        std_image_url, 
        latitude, 
        longitude 
        FROM stadium_locations 
        WHERE team_code = :team_code
    '''
    cursor.execute(query, {'team_code': team_code})
    result = cursor.fetchone()

    conn.close()

    return result
#맛집 정보 조회
def fetch_restaurant_data():
    conn = get_oracle_connection()
    cursor = conn.cursor()

    query = '''
        SELECT 
        STORE_NAME,
        RATING, 
        CATEGORY2, 
        PHONE_NUM, 
        IMG, 
        ADDRESS, 
        LATITUDE, 
        LONGITUDE 
        FROM IRESTAURANTS2
    '''
    cursor.execute(query)
    data = cursor.fetchall()

    conn.close()

    return data
#숙소 정보 조회
def fetch_lodging_data():
    conn = get_oracle_connection()
    cursor = conn.cursor()

    query = '''
        SELECT 
            STORE_NAME,
            RATING, 
            CATEGORY, 
            PHONE_NUM, 
            IMG, 
            ADDRESS, 
            LATITUDE, 
            LONGITUDE 
        FROM LODGING
    '''
    cursor.execute(query)
    data = cursor.fetchall()

    conn.close()

    return data

# 선수 포지션 조회 함수
def get_player_position(name):
    conn = get_oracle_connection()
    cursor = conn.cursor()

    query = '''
        SELECT position FROM ss_players WHERE name = :name
    '''
    cursor.execute(query, {'name': name})
    result = cursor.fetchone()

    conn.close()

    if result:
        return result[0]  # '투수' 또는 '타자'를 반환
    else:
        return None

# 타자 데이터 조회 함수
def fetch_batter_stats(name):
    """
    주어진 타자 이름에 해당하는 성적 데이터를 반환합니다.
    """
    conn = get_oracle_connection()
    cursor = conn.cursor()

    query = '''
        SELECT 
            b.name, 
            p.image_url, 
            b.avg AS AVG, 
            b.hr AS HR, 
            b.rbi AS RBI, 
            b.h AS H, 
            b.pa - b.ab AS BB, 
            b.tb AS TB, 
            b.b2 AS B2, 
            b.b3 AS B3, 
            b.sac AS SAC, 
            b.sf AS SF
        FROM ss_batter_stats b
        JOIN ss_players p ON p.name = b.name AND p.team_code = b.team_code
        WHERE b.name = :name
    '''
    cursor.execute(query, {'name': name})
    batter_stats = cursor.fetchone()

    conn.close()
    return batter_stats

# 투수 데이터 조회 함수
def fetch_pitcher_stats(name):
    try:
        conn = get_oracle_connection()
        cursor = conn.cursor()

        query = '''
           SELECT 
                ps.name, 
                p.image_url, 
                ps.ERA AS ERA, 
                ps.G AS G, 
                ps.W AS W, 
                ps.L AS L, 
                ps.SV AS SV, 
                ps.HLD AS HLD, 
                ps.WPCT AS WPCT, 
                ps.IP AS IP, 
                ps.H AS H, 
                ps.HR AS HR, 
                ps.BB AS BB, 
                ps.HBP AS HBP, 
                ps.SO AS SO, 
                ps.R AS R, 
                ps.ER AS ER, 
                ps.WHIP AS WHIP
            FROM ss_pitcher_stats ps
            JOIN ss_players p ON p.name = ps.name AND p.team_code = ps.team_code
            WHERE ps.name = :name
        '''
        cursor.execute(query, {'name': name})
        pitcher_stats = cursor.fetchone()

        if pitcher_stats is None:
            st.warning(f"{name} 투수 성적 데이터를 찾을 수 없습니다.")

        conn.close()

        return pitcher_stats

    except Exception as e:
        st.error(f"데이터 조회 중 오류 발생: {e}")
        return None


# 키워드와 뉴스 데이터를 가져오는 함수
def fetch_news_and_keywords_from_db(start_date, end_date, team_code):
    connection = get_oracle_connection()
    cursor = connection.cursor()

    keywords_query = """
        SELECT keywords
        FROM news_summary
        WHERE news_date BETWEEN :start_date AND :end_date
        AND team_code = :team_code
    """

    news_query = """
        SELECT title, href
        FROM news_summary
        WHERE news_date BETWEEN :start_date AND :end_date
        AND team_code = :team_code
    """

    cursor.execute(keywords_query, start_date=start_date, end_date=end_date, team_code=team_code)
    rows = cursor.fetchall()

    keywords = []
    for row in rows:
        keywords_str = row[0].read() if isinstance(row[0], cx_Oracle.LOB) else row[0]
        keywords.extend(keywords_str.split(', '))

    cursor.execute(news_query, start_date=start_date, end_date=end_date, team_code=team_code)
    news_rows = cursor.fetchall()

    cursor.close()
    connection.close()

    news_details = [{'title': row[0], 'href': row[1]} for row in news_rows]

    return keywords, news_details


def get_players_by_position(team_code, position):
    """
    주어진 팀 코드와 포지션에 해당하는 선수들의 목록을 반환합니다.
    """
    conn = get_oracle_connection()
    cursor = conn.cursor()

    query = '''
        SELECT name, image_url FROM ss_players
        WHERE team_code = :team_code AND position = :position
    '''
    cursor.execute(query, {'team_code': team_code, 'position': position})
    players = cursor.fetchall()

    conn.close()
    return players if players is not None else []

# expander 사용
def display_player_info_expander(player_data):
    """
    주어진 선수 데이터를 Expander를 사용하여 화면에 표시합니다.
    """
    with st.expander(f"{player_data['name']}의 상세 정보"):
        st.image(player_data['image_url'], use_column_width=True)
        st.write(f"이름: {player_data['name']}")
        if player_data['position'] == '타자':
            st.write(f"타율: {player_data['AVG']}")
            st.write(f"홈런: {player_data['HR']}")
            st.write(f"타점: {player_data['RBI']}")
            st.write(f"안타: {player_data['H']}")
            st.write(f"볼넷: {player_data['BB']}")
            st.write(f"삼진: {player_data['SO']}")
        elif player_data['position'] == '투수':
            st.write(f"ERA: {player_data['ERA']}")
            st.write(f"경기수: {player_data['G']}")
            st.write(f"승: {player_data['W']}")
            st.write(f"패: {player_data['L']}")
            st.write(f"세이브: {player_data['SV']}")
            st.write(f"홀드: {player_data['HLD']}")
            st.write(f"승률: {player_data['WPCT']}")
            st.write(f"이닝: {player_data['IP']}")
            st.write(f"피안타: {player_data['H']}")
            st.write(f"피홈런: {player_data['HR']}")
            st.write(f"볼넷: {player_data['BB']}")
            st.write(f"사구: {player_data['HBP']}")
            st.write(f"탈삼진: {player_data['SO']}")
            st.write(f"실점: {player_data['R']}")
            st.write(f"자책점: {player_data['ER']}")
            st.write(f"WHIP: {player_data['WHIP']}")


def display_player_info(player_data):
    """
    주어진 선수 데이터를 화면에 직접 표시합니다.
    """

    st.header(f"{player_data['name']}의 상세 정보")
    st.image(player_data['image_url'], width=200)
    st.write(f"이름: {player_data['name']}")

    if player_data['position'] == '타자':
        st.write(f"포지션: {player_data['position']}")
        st.write(f"타율 (AVG): {player_data['AVG']}")
        st.write(f"홈런 (HR): {player_data['HR']}")
        st.write(f"타점 (RBI): {player_data['RBI']}")
        st.write(f"안타 (H): {player_data['H']}")
        st.write(f"볼넷 (BB): {player_data['BB']}")
        st.write(f"삼진 (SO): {player_data['SO']}")

    elif player_data['position'] == '투수':
        st.write(f"포지션: {player_data['position']}")
        st.write(f"평균 자책점 (ERA): {player_data['ERA']}")
        st.write(f"경기수 (G): {player_data['G']}")
        st.write(f"승 (W): {player_data['W']}")
        st.write(f"패 (L): {player_data['L']}")
        st.write(f"세이브 (SV): {player_data['SV']}")
        st.write(f"홀드 (HLD): {player_data['HLD']}")
        st.write(f"승률 (WPCT): {player_data['WPCT']}")
        st.write(f"이닝 (IP): {player_data['IP']}")
        st.write(f"피안타 (H): {player_data['H']}")
        st.write(f"피홈런 (HR): {player_data['HR']}")
        st.write(f"볼넷 (BB): {player_data['BB']}")
        st.write(f"사구 (HBP): {player_data['HBP']}")
        st.write(f"탈삼진 (SO): {player_data['SO']}")
        st.write(f"실점 (R): {player_data['R']}")
        st.write(f"자책점 (ER): {player_data['ER']}")
        st.write(f"WHIP: {player_data['WHIP']}")

def load_product_data():
    conn = get_oracle_connection()
    cursor = conn.cursor()

    query = '''
    SELECT name, price, img
    FROM GOODS
    '''

    cursor.execute(query)
    result = cursor.fetchall()

    products = []
    for row in result:
        products.append({
            "name": row[0],
            "price": row[1],
            "image_url": row[2]
        })

    conn.close()
    return products


# 응원 수치 가져오기 함수
def fetch_cheer_data():
    conn = get_oracle_connection()
    cursor = conn.cursor()

    query = """
    SELECT TEAM1_NAME, TEAM1_CHEER_COUNT, TEAM2_NAME, TEAM2_CHEER_COUNT
    FROM MATCH_CHEER_STATS
    WHERE MATCH_DATE = TO_DATE(:today, 'YYYYMMDD')
    """

    today = time.strftime('%Y%m%d')
    cursor.execute(query, {'today': today})
    result = cursor.fetchall()
    cursor.close()
    conn.close()

    # DataFrame으로 변환
    data = []
    for row in result:
        data.append({
            'team1_name': row[0],
            'team1_cheer': row[1],
            'team2_name': row[2],
            'team2_cheer': row[3]
        })

    return pd.DataFrame(data)


# Streamlit 앱 설정
st.set_page_config(
    page_title="Home in Run",
    layout="wide",
    page_icon="./team_logo2/baseball.png"
)

team_codes = {
    "삼성 라이온즈": "SS",
    "두산 베어스": "OB",
    "롯데 자이언츠": "LT",
    "LG 트윈스": "LG",
    "KIA 타이거즈": "HT",
    "한화 이글스": "HH",
    "NC 다이노스": "NC",
    "SSG 랜더스": "SK",
    "키움 히어로즈": "WO",
    "KT WIZ": "KT"
}
team_colors = {
    "KIA": "#E4002B",    # 기존 색상 (빨간색)
    "삼성": "#0033A0",    # 기존 색상 (파란색)
    "LG": "#B33A3A",      # 기존 색상 (짙은 빨간색)
    "두산": "#002F6C",    # 기존 색상 (짙은 남색)
    "KT": "#F76C6C",      # 기존 색상 (밝은 빨간색)
    "한화": "#FF6600",    # 기존 색상 (주황색)
    "SSG": "#D9B25C",     # 기존 색상 (금색)
    "롯데": "#002A5C",    # 조정된 색상 (진한 파란색)
    "NC": "#0077B6",      # 조정된 색상 (밝은 청색)
    "키움": "#D57A77"     # 기존 색상 (연한 갈색)
}
team_logo_url = {
    "한화": "https://i.namu.wiki/i/4uBeV5iCunivTpOUHMvJxpUoyWeFpPNTji89NglI-ePm1_dBCpMoIUlCKiftH3HwxqBlHGOwg52_VDT9xfyVzt4u4sNj50N6CdPcGHfjbE9bL3la3JI2AVenVKHDhykTKaag1F3HApYdGq6zr8SGaA.svg",
    "삼성": "https://i.namu.wiki/i/fmaqumWabeh7-9rGNKKEyEpx6Up2b89HfeLLObHuH7JOZqI5puxTvL7dYR7-jBo5ybSRVXvz7YXERs79-UkNWIN9z9IE4YAxRblmTc6BK-DCL7NJzpuB5UkTQON7MPJUJWMPG3Psi2KUMRKnJeD60Q.svg",
    "KIA": "https://i.namu.wiki/i/irkN-6y3WF9E8Ic50vBi-MFMHF-HVPnQdFVmgK8l35Q-I5rL9KI3JwzfwlnwGeS29I_kPakiKJmCN6LlvcLuBvl-br1vPZBvpyMhXtFR6o6s4sgyAVuhGyIoEk6nc_6Jp7GG_6NUMOrMI6YVVm11SQ.svg",
    "롯데": "https://i.namu.wiki/i/wUlggjk4TbScUHrz95yAKsgnbkbgt2sCzSEIDRy5Bw_mPSHYi78tlPwUmIndo_Ms_1lSIwJDHajqJdrRyRwueAUhEmFq4GGX7kO_CZpFBAYh7yQHaiuO8kcQumK-FRPXi8ao16KdYsHp626SEMIbiQ.svg",
    "NC": "https://i.namu.wiki/i/tP1xo26er7jQolB6jKCc29pDcSD3guJNOC2U08lwbAFUzDkAQOVoaAdTYjuIuMf5cAOi2xJO1Lklxqk2GfAgswTHPSr8v6Ev0eBCEhA8oiUdWeZugigHLf1Rsyd1BFKw3An8-33_no2tz7ZBd8HpCg.svg",
    "두산": "https://i.namu.wiki/i/lE9Jslm6XgR5YFN2hUvS7DdO6kLxR8wwTAti8IW-8bOtWqtl_IhI9ANqlj3CzvNXEnJuwkX3z7Pe-T1JNowA_DDAyVvpj5JEABthnOfyM6mFa-2nada30lM5edgYb80KuZHZeVImwesk1ejAYp6i_g.svg",
    "SSG": "https://i.namu.wiki/i/eiKOoI_edky-xU7iaIGJ06E4X2USEtIHDhRrHIzjHdrEKLSxnxnvBIZbgMUm7bCMI1MWtjNCFFjphu04cUCI4rDBqUumK1cC-HHHELAhkVk_3NjRmnWUtljfP26QEndnEvfqLfwInEjIckyybaw-PQ.svg",
    "KT": "https://i.namu.wiki/i/T-mDdEnWT-SpUXdoqYSmqEOueBOiOTtxgARg6pUVsilKDFrTMH7LyyGCfwpMbhcgi_nqKFbQSF3Rk6EBcR84Aw.svg",
    "키움": "https://i.namu.wiki/i/64LOfXRrCCTR3P3ZBIlSYnGXDaOL0qBNQdj4YTlCzLO1HVY4xoYgezMw0_Q_TpNZRRxNQJPMvSCP0YPMMI4rJN2TB_ELzgdxw89Tc0wJRB-bUE_0VVYwiTdPu88APMtmyXngggnrJU-FWM1OzwDtbg.svg",
    "LG": "https://i.namu.wiki/i/NPpaSSKmDi5VrwqzDQq5HB3noZQu9bvU43S9e84xKzF8MDO5Lw8lyKVfbXdy2-Yst-bOPeSGdQLM4B1aIXluyAekDYvAgO5iWGI25HLm7ywE4j-1TZTSxecFJPurLYXtymixGuI46noWnIKYu2lxKQ.svg"
}
stadium_names = {
    "대구": "삼성 라이온즈 파크",
    "잠실": "잠실 야구장",
    "사직": "사직 야구장",
    "광주": "광주-KIA 챔피언스 필드",
    "대전": "대전 한화생명이글스파크",
    "창원": "창원 NC파크",
    "인천": "인천 SSG 랜더스필드",
    "고척": "고척 스카이돔",
    "수원": "수원 KT위즈파크"
}
UPDATE_INTERVAL = 5
#실시간 업데이트 주기 10(초)
st_autorefresh(interval=UPDATE_INTERVAL * 1000, key="data_refresh")

team_logo_path = "team_logo2/"

# 메인 페이지
# 페이지 네비게이션 상태 초기화
if 'highlight_page_index' not in st.session_state:
    st.session_state.highlight_page_index = 1

if 'recommendation_page_index' not in st.session_state:
    st.session_state.recommendation_page_index = 1

# 사이드바 메뉴 설정
st.sidebar.title("메뉴")
menu = st.sidebar.radio("선택하세요", ("메인페이지", "야구뉴스 한눈에", "구단별 추천 영상","구단별 선수 조회", "구장 주변 맛집&숙소 정보", "KBO 마켓"))

if menu == "메인페이지":
    col1, col2 = st.columns([1, 1.3])  # 열 비율 설정 (1:5 비율)

    with col1:
        st.image(f"{team_logo_path}kbo.png",width=150)  # KBO 이미지 경로를 지정

    with col2:
        st.title("Home in Run")
# if menu == "메인페이지":
#     col1, col2 = st.columns([1, 1.3])  # 열 비율 설정 (1:1.3 비율)
#
#     with col1:
#         st.markdown(
#             """
#             <img src="https://i.namu.wiki/i/cIAVSZg-lGmELZYXp2yJFFF7rlcUlF7DoOY8hA9mmzBqILjv9YhYWuGwzgmqlFgi3IW6ymtowA24uCy-SwBIbg.svg" width="100"/>
#             """,
#             unsafe_allow_html=True
#         )  # KBO 이미지 URL을 사용하여 표시

    with col2:
        st.title("Home in Run")
    if 'selected_date' not in st.session_state:
        st.session_state.selected_date = datetime.now().date()

    # 날짜 조작 버튼
    col1, col2, col3 = st.columns([1, 1, 0.5])
    with col1:
        if st.button("< 이전 날짜"):
            st.session_state.selected_date -= timedelta(days=1)
    with col2:
        current_date = st.session_state.selected_date
        st.markdown(f"### {current_date.strftime('%Y-%m-%d')} 경기 일정")
    with col3:
        if st.button("다음 날짜 >"):
            st.session_state.selected_date += timedelta(days=1)

    # 경기 일정 가져오기
    schedule_df = create_schedule_with_weather_df(current_date.strftime('%Y-%m-%d'))

    # 일정이 없을 경우 메시지 표시
    if schedule_df.empty:
        st.write("해당 날짜의 경기가 없습니다.")
    else:
        for _, row in schedule_df.iterrows():
            team1 = row['Team 1']
            match_time = row['Time']
            team2 = row['Team 2']
            home_indicator = row['Home Indicator']
            low_temp = row['Low Temp']
            high_temp = row['High Temp']
            rain_prob = row['Rain Probability']
            location = row['Location']

            # 팀 로고 URL 가져오기
            team1_logo_url = team_logo_url.get(team1, "")
            team2_logo_url = team_logo_url.get(team2, "")

            # 로고와 함께 경기 정보 표시
            st.markdown(f"""
                <div style='display: flex; justify-content: center; align-items: center; margin-bottom: 20px;'>
                    <div style='text-align: center; margin-right: 20px;'>
                        <div style='display: flex; justify-content: center; align-items: center;'>
                            <div style='margin-right: 10px;'>
                                <img src='{team1_logo_url}' style='width: 100px; height: 100px;'/>
                                <p>{team1}</p>
                            </div>
                            <div style='margin: 0 20px;'>
                                <p>{match_time}</p>
                            </div>
                            <div style='margin-left: 10px;'>
                                <img src='{team2_logo_url}' style='width: 100px; height: 100px;'/>
                                <p>{team2}{home_indicator}</p>
                            </div>
                        </div>
                    </div>
                    <div style='text-align: left;'>
                        <p>최고기온: {high_temp}</p>
                        <p>최저기온: {low_temp}</p>
                        <p>강우확률: {rain_prob}</p>
                        <p>위치: {stadium_names.get(location, "정보 없음")}</p>
                    </div>
                </div>
            """, unsafe_allow_html=True)

    col1, col2 = st.columns([0.5, 3])

    with col1:
        # 서브헤더와 함께 응원 수치를 표시합니다.
        st.subheader("실시간 응원 수치")

    with col2:
        # HTML과 JavaScript를 포함한 컴포넌트를 사용하여 시계를 구현합니다.
        components.html("""
            <html>
                <body>
                    <div id="clock" style="font-size: 24px; font-weight: bold;"></div>
                    <script>
                        function updateClock() {
                            const now = new Date();
                            const hours = String(now.getHours()).padStart(2, '0');
                            const minutes = String(now.getMinutes()).padStart(2, '0');
                            const seconds = String(now.getSeconds()).padStart(2, '0');
                            document.getElementById('clock').innerText = hours + ':' + minutes + ':' + seconds;
                        }
                        setInterval(updateClock, 1000);
                        updateClock();
                    </script>
                </body>
            </html>
        """)

    # 응원 수치 데이터를 세션 상태에서 가져오거나 새로 가져옵니다.
    if 'cheer_data' not in st.session_state:
        st.session_state.cheer_data = fetch_cheer_data()

    # 현재 응원 수치 가져오기
    cheer_data = fetch_cheer_data()


    # 이전 응원 수치를 세션 상태에서 가져옵니다. 없으면 초기화합니다.
    if 'previous_cheer_data' not in st.session_state:
        st.session_state.previous_cheer_data = pd.DataFrame(
            columns=['team1_name', 'team1_cheer', 'team2_name', 'team2_cheer'])



    if not cheer_data.empty:
        # 이전 수치와 비교하여 증감량을 계산합니다.
        if not st.session_state.previous_cheer_data.empty:
            merged_data = cheer_data.merge(st.session_state.previous_cheer_data, on=['team1_name', 'team2_name'],
                                           suffixes=('_current', '_previous'))

            # 증감량 계산
            merged_data['team1_cheer_change'] = merged_data['team1_cheer_current'] - merged_data['team1_cheer_previous']
            merged_data['team2_cheer_change'] = merged_data['team2_cheer_current'] - merged_data['team2_cheer_previous']

            num_pie_charts = len(merged_data)
            num_rows = (num_pie_charts + 3) // 4  # 필요한 행 수 계산

            for row_idx in range(num_rows):
                cols = st.columns(4)  # 각 행에 4개의 열 생성
                for col_idx in range(4):
                    chart_index = row_idx * 4 + col_idx
                    if chart_index >= num_pie_charts:
                        break
                    row = merged_data.iloc[chart_index]
                    pie_chart_data = pd.DataFrame({
                        'Team': [row['team1_name'], row['team2_name']],
                        'Cheer Count': [row['team1_cheer_current'], row['team2_cheer_current']]
                    })

                    with cols[col_idx]:
                        fig = px.pie(pie_chart_data, names='Team', values='Cheer Count',
                                     color='Team', color_discrete_map=team_colors,
                                     title=f"{row['team1_name']} vs {row['team2_name']}",
                                     labels={'Cheer Count': '응원 수치'}
                                     )
                        fig.update_traces(textinfo='label',  # 팀 이름만 표시
                                          textposition='inside',
                                          texttemplate='<b>%{label}</b>')  # 굵게 표시
                        st.plotly_chart(fig, use_container_width=True)

                    # Metric을 표시
                    with cols[col_idx]:
                        st.metric(
                            label=f"{row['team1_name']}팀 응원 수",
                            value=f"{row['team1_cheer_current']:,}",
                            delta=f"{row['team1_cheer_change']:,}" if row['team1_cheer_change'] != 0 else None,
                            delta_color="inverse" if row['team1_cheer_change'] < 0 else "normal"
                        )
                        st.metric(
                            label=f"{row['team2_name']}팀 응원 수",
                            value=f"{row['team2_cheer_current']:,}",
                            delta=f"{row['team2_cheer_change']:,}" if row['team2_cheer_change'] != 0 else None,
                            delta_color="inverse" if row['team2_cheer_change'] < 0 else "normal"
                        )

        # 현재 수치를 이전 수치로 업데이트
        st.session_state.previous_cheer_data = cheer_data


    # 데이터 로드
    df_rank = load_rank_data()
    df_all_rank = load_all_rank_data()

    # 컬럼 설정
    col1, col2 = st.columns(2)

    # 첫 번째 컬럼: KBO 리그 팀 순위
    with col1:
        st.subheader("KBO 현재 리그 팀 순위")
        st.markdown(
            f"""
                    <div style='display: flex; justify-content: center;'>
                        {df_rank.to_html(index=False)}
                    </div>
                    """,
            unsafe_allow_html=True
        )

    # 두 번째 컬럼: 팀 순위 변화 라인 차트
    with col2:
        st.subheader("팀 순위 변화")

        if df_all_rank.empty:
            st.write("순위 데이터가 없습니다.")
        else:
            # 데이터 피벗
            df_all_rank_pivot = df_all_rank.pivot_table(index='날짜', columns='팀명', values='순위')

            # Altair 차트 생성
            base = alt.Chart(df_all_rank.reset_index()).mark_line().encode(
                x=alt.X('날짜:T', title='날짜'),
                y=alt.Y('순위:Q', title='순위', scale=alt.Scale(domain=[10, 1])),
                color=alt.Color('팀명:N',
                                scale=alt.Scale(domain=list(team_colors.keys()), range=list(team_colors.values())))
            ).properties(
                width=400,  # 너비 조정
                height=400  # 높이 조정
            )

            st.altair_chart(base, use_container_width=True)

    st.subheader("최신 하이라이트 영상")

    videos_per_page = 4
    total_videos = get_total_videos_count()  # 전체 비디오 수 가져오기
    total_pages = (total_videos + videos_per_page - 1) // videos_per_page

    # 현재 페이지의 비디오 목록을 가져오기
    start_idx = (st.session_state.highlight_page_index - 1) * videos_per_page
    end_idx = start_idx + videos_per_page
    videos_to_display = get_videos_from_db(limit=videos_per_page, offset=start_idx)

    # 동영상 목록을 페이지로 표시
    if videos_to_display:
        cols = st.columns(len(videos_to_display))
        for col, video in zip(cols, videos_to_display):
            with col:
                st.markdown(f"""
                    <a href="{video['video_url']}" target="_blank">
                        <img src="{video['thumbnail_url']}" alt="{video['title']}" style="width: 100%;"/>
                    </a>
                    <p>{video['title']}</p>
                """, unsafe_allow_html=True)
    else:
        st.write("현재 페이지에 비디오가 없습니다.")

    # 페이지네이션 버튼
    col1, col2, col3 = st.columns([1, 1, 0.5])
    with col1:
        if st.button("이전 페이지") and st.session_state.highlight_page_index > 1:
            st.session_state.highlight_page_index -= 1

    with col2:
        st.write(f"페이지 {st.session_state.highlight_page_index} / {total_pages}")

    with col3:
        if st.button("다음 페이지") and st.session_state.highlight_page_index < total_pages:
            st.session_state.highlight_page_index += 1

elif menu == "야구뉴스 한눈에":
    st.title("야구뉴스 한눈에")

    tabs = st.tabs(list(team_codes.keys()))

    for i, (team_name, team_code) in enumerate(team_codes.items()):
        with tabs[i]:
            col1, empty_col, col2 = st.columns([1, 0.5, 5])

            with col1:
                st.image(f"{team_logo_path}{team_code.lower()}.png", width=150)

            with col2:
                st.header(f"{team_name} 팀 페이지")
                st.markdown("### 여기는 {} 팀 페이지입니다.".format(team_name))
# elif menu == "야구뉴스 한눈에":
#     st.title("야구뉴스 한눈에")
#
#     tabs = st.tabs(list(team_codes.keys()))
#
#     for i, (team_name, team_code) in enumerate(team_codes.items()):
#         with tabs[i]:
#             col1, empty_col, col2 = st.columns([1, 0.5, 5])
#
#             with col1:
#                 # team_codes의 키와 team_logo_url의 키가 일치하도록 변환
#                 team_logo_key = {
#                     "삼성 라이온즈": "삼성",
#                     "두산 베어스": "두산",
#                     "롯데 자이언츠": "롯데",
#                     "LG 트윈스": "LG",
#                     "KIA 타이거즈": "KIA",
#                     "한화 이글스": "한화",
#                     "NC 다이노스": "NC",
#                     "SSG 랜더스": "SSG",
#                     "키움 히어로즈": "키움",
#                     "KT WIZ": "KT"
#                 }.get(team_name, team_name)
#
#                 # 팀 로고 URL을 사용하여 Markdown으로 이미지 표시
#                 st.markdown(
#                     f"![{team_name} Logo]({team_logo_url.get(team_logo_key, '')})",
#                     unsafe_allow_html=True
#                 )
#
#             with col2:
#                 st.header(f"{team_name} 팀 페이지")
#                 st.markdown(f"### 여기는 {team_name} 팀 페이지입니다.")

            st.markdown("### 기간별 뉴스 조회")

            with st.form(key=f"form_{team_code}"):
                col1, col2 = st.columns([4, 4])

                with col1:
                    start_date = st.date_input("시작 날짜", min_value=dt.date(2020, 1, 1),
                                               max_value=dt.date.today(), key=f"start_date_{team_code}")

                with col2:
                    end_date = st.date_input("종료 날짜", min_value=dt.date(2020, 1, 1),
                                             max_value=dt.date.today(), key=f"end_date_{team_code}")

                submit_button = st.form_submit_button("조회")

                if submit_button:
                    if start_date > end_date:
                        st.error("종료 날짜는 시작 날짜보다 늦어야 합니다.")
                    else:
                        with st.spinner("키워드와 뉴스 데이터를 가져오는 중입니다..."):
                            keywords, news_details = fetch_news_and_keywords_from_db(start_date, end_date, team_code)

                            if not keywords:
                                st.warning("해당 기간에 키워드가 없습니다.")
                            else:
                                hannanum = Hannanum()
                                word_list = hannanum.nouns(' '.join(keywords))

                                font_path = 'KBO Dia Gothic_medium.ttf'  # 워드클라우드 폰트 설정
                                wordcloud = WordCloud(
                                    font_path=font_path,
                                    width=800,
                                    height=800,
                                    background_color="white"
                                ).generate_from_frequencies(Counter(word_list))

                                st.session_state[team_code] = {
                                    'wordcloud': wordcloud.to_array(),
                                    'news_details': news_details
                                }

            if team_code in st.session_state:
                st.image(st.session_state[team_code]['wordcloud'], caption=f"{team_name} 관련 뉴스 워드 클라우드",
                         width=600)

                news_details = st.session_state[team_code]['news_details']
                num_per_page = 5
                total_pages = (len(news_details) + num_per_page - 1) // num_per_page

                page = st.selectbox("페이지 선택", range(1, total_pages + 1), key=f"page_select_{team_code}")
                start_index = (page - 1) * num_per_page
                end_index = min(page * num_per_page, len(news_details))

                st.markdown("### 관련 뉴스")
                for article in news_details[start_index:end_index]:
                    st.markdown(f"[{article['title']}]({article['href']})")

elif menu == "구단별 추천 영상":
    st.title("구단별 추천 영상")

    tabs = st.tabs(list(team_codes.keys()))

    for i, (team_name, team_code) in enumerate(team_codes.items()):
        with tabs[i]:
            st.header(f"{team_name} 팀의 추천 영상")

    videos_per_page = 4
    total_videos = get_total_emotion_count()  # 전체 비디오 수 가져오기
    total_pages = (total_videos + videos_per_page - 1) // videos_per_page

    # 현재 페이지의 비디오 목록을 가져오기
    start_idx = (st.session_state.recommendation_page_index - 1) * videos_per_page
    end_idx = start_idx + videos_per_page
    videos_to_display = get_rcmd_videos_from_db(limit=videos_per_page, offset=start_idx)

    if videos_to_display:
        cols = st.columns(len(videos_to_display))
        for col, video in zip(cols, videos_to_display):
            with col:
                st.markdown(f"""
                    <a href="{video['video_url']}" target="_blank">
                        <img src="{video['thumbnail_url']}" alt="{video['title']}" style="width: 100%;"/>
                    </a>
                    <p>{video['title']}</p>
                """, unsafe_allow_html=True)
    else:
        st.write("현재 페이지에 비디오가 없습니다.")

    # 페이지네이션 버튼
    col1, col2, col3 = st.columns([2, 2, 1])
    with col1:
        if st.button("이전 페이지", key="recommendation_prev") and st.session_state.recommendation_page_index > 1:
            st.session_state.recommendation_page_index -= 1

    with col2:
        st.write(f"페이지 {st.session_state.recommendation_page_index} / {total_pages}")

    with col3:
        if st.button("다음 페이지", key="recommendation_next") and st.session_state.recommendation_page_index < total_pages:
            st.session_state.recommendation_page_index += 1

elif menu == "구단별 선수 조회":
    st.title("구단별 선수 조회")

    # 상단에 고정할 expander
    # selected_player_expander = st.expander("선수 정보 보기", expanded=True)

    tabs = st.tabs(list(team_codes.keys()))

    for i, (team_name, team_code) in enumerate(team_codes.items()):
        with tabs[i]:
            st.header(f"{team_name} 선수 조회")

            # 포지션 선택
            position = st.radio("포지션 선택", ["타자", "투수"], key=f"position_{team_code}")

            # 선수 목록 조회
            players = get_players_by_position(team_code, position)
            selected_player_expander = st.expander(f"선수 정보 보기", expanded=False)
            if players:
                st.subheader(f"{team_name} {position} 목록")

                # 선수 사진을 한 줄에 4개씩 표시
                cols = st.columns(4)  # 4개의 열 생성
                for idx, player in enumerate(players):
                    player_name, image_url = player
                    col_idx = idx % 4  # 0부터 3까지 반복

                    with cols[col_idx]:
                        # 버튼을 고유하게 생성
                        button_key = f"btn_{team_code}_{player_name}_{idx}"
                        if st.button(f"{player_name}", key=button_key):
                            st.session_state.selected_player_name = player_name
                        st.image(image_url, caption=player_name, use_column_width=True)

                # 선택된 선수의 성적 데이터 조회 및 정보 표시
                if 'selected_player_name' in st.session_state:
                    selected_player_name = st.session_state.selected_player_name
                    st.session_state.selected_player_name = None  # 선택된 선수 이름 초기화

                    with selected_player_expander:  # expander에 정보 표시
                        # st.header(f"{selected_player_name}의 상세 정보")

                        # 포지션 확인
                        position = get_player_position(selected_player_name)

                        if position == '타자':
                            batter_stats = fetch_batter_stats(selected_player_name)
                            if batter_stats:
                                player_data = {
                                    'name': batter_stats[0],
                                    'position': position,
                                    'AVG': batter_stats[2],
                                    'HR': batter_stats[3],
                                    'RBI': batter_stats[4],
                                    'H': batter_stats[5],
                                    'BB': batter_stats[6],
                                    'SO': batter_stats[7],
                                    'image_url': batter_stats[1]
                                }
                                display_player_info(player_data)  # 정보를 직접 표시
                            else:
                                st.warning("타자 성적 데이터를 찾을 수 없습니다.")
                        elif position == '투수':
                            pitcher_stats = fetch_pitcher_stats(selected_player_name)
                            if pitcher_stats:
                                player_data = {
                                    'position': position,
                                    'name': pitcher_stats[0],
                                    'image_url': pitcher_stats[1],
                                    'ERA': pitcher_stats[2],
                                    'G': pitcher_stats[3],
                                    'W': pitcher_stats[4],
                                    'L': pitcher_stats[5],
                                    'SV': pitcher_stats[6],
                                    'HLD': pitcher_stats[7],
                                    'WPCT': pitcher_stats[8],
                                    'IP': pitcher_stats[9],
                                    'H': pitcher_stats[10],
                                    'HR': pitcher_stats[11],
                                    'BB': pitcher_stats[12],
                                    'HBP': pitcher_stats[13],
                                    'SO': pitcher_stats[14],
                                    'R': pitcher_stats[15],
                                    'ER': pitcher_stats[16],
                                    'WHIP': pitcher_stats[17]
                                }
                                display_player_info(player_data)  # 정보를 직접 표시
                            else:
                                st.warning("투수 성적 데이터를 찾을 수 없습니다.")
                        else:
                            st.warning("알 수 없는 포지션입니다.")
            else:
                st.warning(f"{team_name} {position} 목록을 찾을 수 없습니다.")



elif menu == "구장 주변 맛집&숙소 정보":
    st.title("구장 주변 맛집&숙소 정보")
    tabs = st.tabs(list(team_codes.keys()))

    for i, (team_name, team_code) in enumerate(team_codes.items()):
        with tabs[i]:
            # 구장 정보를 데이터베이스에서 가져옵니다
            stadium_data = get_stadium_data(team_code)

            if stadium_data:
                stadium_name, stadium_image_url, stadium_lat, stadium_lon = stadium_data

                # 구장 이름을 탭 제목으로 설정
                st.header(f"{stadium_name} 주변 맛집&숙소 정보")

                # 필터 및 검색 기능 추가
                st.subheader("필터링 및 검색")

                # 기본 지도 설정 (팀 구장 위치로)
                location = [stadium_lat, stadium_lon]
                m = folium.Map(location=location, zoom_start=14)

                # 라디오 버튼으로 표시할 항목 선택
                display_option = st.radio(
                    "표시할 항목 선택",
                    ["모두 표시", "맛집만 표시", "숙소만 표시"],
                    index=0,  # 기본값으로 모두 표시
                    key=f"display_option_{team_code}"  # 각 팀 코드로 고유한 키 생성
                )
                # 구장 위치에 빨간색 마커 추가
                folium.Marker(
                    location=location,
                    popup=folium.Popup(f"""
                        <div style='width:300px;'>
                            <strong>{stadium_name}</strong><br>
                            <img src='{stadium_image_url}' width='250'><br>
                        </div>
                    """, max_width=300),
                    icon=folium.Icon(color='red', icon='baseball-ball', prefix='fa')
                ).add_to(m)

                # 맛집과 숙소 데이터 가져오기
                restaurants = fetch_restaurant_data()
                lodgings = fetch_lodging_data()

                # 음식점 카테고리 선택 박스 추가
                category_option = st.selectbox(
                    "카테고리 선택",
                    ["전체", "한식", "양식", "일식", "주류", "기타"],
                    key=f"category_option_{team_code}"
                )

                # 선택된 옵션에 따라 마커 추가
                if display_option == "모두 표시" or display_option == "맛집만 표시":
                    # 선택된 카테고리에 맞게 음식점 데이터 필터링
                    if category_option != "전체":
                        filtered_restaurants = [r for r in restaurants if r[2] == category_option]
                    else:
                        filtered_restaurants = restaurants

                    # 평점이 높은 순서대로 정렬
                    filtered_restaurants.sort(key=lambda x: x[1], reverse=True)

                    for j, restaurant in enumerate(filtered_restaurants):
                        store_name, rating, category, phone_num, img_url, address, latitude, longitude = restaurant
                        folium.Marker(
                            location=[latitude, longitude],
                            popup=folium.Popup(f"""
                                    <div style='width:200px;'>
                                        <strong>{store_name}</strong><br>
                                        평점: {rating}<br>
                                        카테고리: {category}<br>
                                        전화번호: {phone_num}<br>
                                        <img src='{img_url}' width='150'><br>
                                        주소: {address}
                                    </div>
                                """, max_width=300),
                            tooltip=store_name,
                            icon=folium.Icon(color='blue', icon='utensils', prefix='fa'),
                            key=f"restaurant_marker_{j}"
                        ).add_to(m)

                if display_option == "모두 표시" or display_option == "숙소만 표시":
                    for j, lodging in enumerate(lodgings):
                        store_name, rating, category, phone_num, img_url, address, latitude, longitude = lodging
                        folium.Marker(
                            location=[latitude, longitude],
                            popup=folium.Popup(f"""
                                    <div style='width:200px;'>
                                        <strong>{store_name}</strong><br>
                                        평점: {rating}<br>
                                        카테고리: {category}<br>
                                        전화번호: {phone_num}<br>
                                        <img src='{img_url}' width='150'><br>
                                        주소: {address}
                                    </div>
                                """, max_width=300),
                            tooltip=store_name,
                            icon=folium.Icon(color='green', icon='bed', prefix='fa'),
                            key=f"lodging_marker_{j}"
                        ).add_to(m)

                # Streamlit에 Folium 지도 표시
                st_folium(m, width=700, height=500)
            else:
                st.warning(f"{team_name} 구장 정보를 찾을 수 없습니다.")

elif menu == "KBO 마켓":
    st.title("KBO 리그의 다양한 상품을 만나보세요")
    products = load_product_data()

    # 상품 나열
    st.subheader("상품 리스트")

    # 한 줄에 5개씩 나열
    num_columns = 5
    cols = st.columns(num_columns)

    for idx, product in enumerate(products):
        col = cols[idx % num_columns]
        with col:
            st.image(product["image_url"], width=170)
            st.write(f"**{product['name']}**")
            st.write(product["price"])

        # 5개 상품을 나열한 후 다음 줄로 넘어감
        if (idx + 1) % num_columns == 0:
            st.write("")  # 다음 줄로 이동하기 위해 빈 줄 추가

