from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import cx_Oracle
import time
from concurrent.futures import ThreadPoolExecutor
import schedule

# 데이터베이스 연결 함수
def get_oracle_connection():
    dsn_tns = cx_Oracle.makedsn('localhost', '1521', sid='xe')
    connection = cx_Oracle.connect(user='base_man', password='1111', dsn=dsn_tns)
    return connection


# 응원 수치를 숫자로 변환
def parse_cheer_count(count_str):
    try:
        # 쉼표를 제거하고 정수로 변환
        return int(count_str.replace(',', ''))
    except ValueError:
        # 변환에 실패할 경우 0 반환 (오류 처리)
        return 0


# 오늘의 경기 일정 가져오기
def fetch_today_matches():
    conn = get_oracle_connection()
    cursor = conn.cursor()
    today = time.strftime('%Y/%m/%d')
    query = """
    SELECT MATCH_DATE, TEAM1_CODE, TEAM2_CODE
    FROM MATCH_SCHEDULE
    WHERE MATCH_DATE = TO_DATE(:today, 'YYYY/MM/DD')
    """
    cursor.execute(query, {'today': today})
    matches = cursor.fetchall()
    cursor.close()
    conn.close()
    return matches


# 팀 이름 가져오기
def fetch_team_names():
    conn = get_oracle_connection()
    cursor = conn.cursor()
    query = """
    SELECT TEAM_CODE, TEAM_NAME
    FROM TEAM
    """
    cursor.execute(query)
    team_names = cursor.fetchall()
    cursor.close()
    conn.close()

    # 팀 코드와 이름을 매핑하는 딕셔너리 생성
    team_mapping = {team_code: team_name for team_code, team_name in team_names}
    return team_mapping


# Selenium 드라이버 설정
def get_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")  # 헤드리스 모드로 실행
    chrome_options.add_argument("--disable-gpu")  # GPU 가속 비활성화
    chrome_options.add_argument("--no-sandbox")  # 샌드박스 비활성화
    chrome_options.add_argument("--disable-dev-shm-usage")  # Dev/shm 사용 비활성화
    chrome_options.add_argument("--disable-extensions")  # 확장 프로그램 비활성화

    service = Service(ChromeDriverManager().install())  # ChromeDriver 자동 설치 및 관리
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver


# 응원 수치 크롤링
def get_cheer_count(driver):
    # 페이지가 로드되기를 3초 동안 기다림
    time.sleep(3)  # 물리적으로 3초 대기

    # 요소가 페이지에 로드되었는지 확인하기 위해 다시 시도
    left_team_count_element = driver.find_element(By.CSS_SELECTOR, '.CheerVS_left_team__3uqU9 .CheerVS_count__3K7p8')
    right_team_count_element = driver.find_element(By.CSS_SELECTOR, '.CheerVS_right_team__2cmbF .CheerVS_count__3K7p8')

    # 응원 수치 추출 및 전처리
    cheer_counts = {
        'left_team_count': parse_cheer_count(left_team_count_element.text),
        'right_team_count': parse_cheer_count(right_team_count_element.text)
    }
    return cheer_counts


# URL 생성
def generate_url(match):
    match_date, team1_code, team2_code = match
    date_str = match_date.strftime('%Y%m%d')  # '20240904'
    return f'https://m.sports.naver.com/game/{date_str}{team1_code}{team2_code}02024/cheer'


# 경기 응원 수치 크롤링
def crawl_match_cheer(match, team_names):
    url = generate_url(match)
    driver = get_driver()
    driver.get(url)

    cheer_counts = get_cheer_count(driver)
    driver.quit()

    team1_code, team2_code = match[1], match[2]
    return {
        'url': url,
        'left_team_name': team_names.get(team1_code, 'Unknown'),
        'left_team_count': cheer_counts['left_team_count'],
        'right_team_name': team_names.get(team2_code, 'Unknown'),
        'right_team_count': cheer_counts['right_team_count']
    }


def upsert_match_cheer_stats(data):
    conn = get_oracle_connection()
    cursor = conn.cursor()

    # MERGE 쿼리
    merge_query = """
    MERGE INTO MATCH_CHEER_STATS target
    USING (SELECT :MATCH_DATE AS MATCH_DATE,
                  :TEAM1_CODE AS TEAM1_CODE,
                  :TEAM1_NAME AS TEAM1_NAME,
                  :TEAM1_CHEER_COUNT AS TEAM1_CHEER_COUNT,
                  :TEAM2_CODE AS TEAM2_CODE,
                  :TEAM2_NAME AS TEAM2_NAME,
                  :TEAM2_CHEER_COUNT AS TEAM2_CHEER_COUNT,
                  :URL AS URL,
                  :RETRIEVED_AT AS RETRIEVED_AT
           FROM dual) source
    ON (target.MATCH_DATE = source.MATCH_DATE
        AND target.TEAM1_CODE = source.TEAM1_CODE
        AND target.TEAM2_CODE = source.TEAM2_CODE)
    WHEN MATCHED THEN
        UPDATE SET target.TEAM1_NAME = source.TEAM1_NAME,
                   target.TEAM1_CHEER_COUNT = source.TEAM1_CHEER_COUNT,
                   target.TEAM2_NAME = source.TEAM2_NAME,
                   target.TEAM2_CHEER_COUNT = source.TEAM2_CHEER_COUNT,
                   target.URL = source.URL,
                   target.RETRIEVED_AT = source.RETRIEVED_AT
    WHEN NOT MATCHED THEN
        INSERT (MATCH_DATE, TEAM1_CODE, TEAM1_NAME, TEAM1_CHEER_COUNT,
                TEAM2_CODE, TEAM2_NAME, TEAM2_CHEER_COUNT, URL, RETRIEVED_AT)
        VALUES (source.MATCH_DATE, source.TEAM1_CODE, source.TEAM1_NAME, source.TEAM1_CHEER_COUNT,
                source.TEAM2_CODE, source.TEAM2_NAME, source.TEAM2_CHEER_COUNT, source.URL, source.RETRIEVED_AT)
    """

    # 삽입 또는 업데이트할 데이터
    merge_data = {
        'MATCH_DATE': data['match_date'],
        'TEAM1_CODE': data['team1_code'],
        'TEAM1_NAME': data['left_team_name'],
        'TEAM1_CHEER_COUNT': data['left_team_count'],
        'TEAM2_CODE': data['team2_code'],
        'TEAM2_NAME': data['right_team_name'],
        'TEAM2_CHEER_COUNT': data['right_team_count'],
        'URL': data['url'],
        'RETRIEVED_AT': time.strftime('%Y-%m-%d %H:%M:%S')
    }

    # MERGE 작업 수행
    try:
        cursor.execute(merge_query, merge_data)
        conn.commit()  # 변경사항 저장
    except cx_Oracle.DatabaseError as e:
        print(f"Database error occurred: {e}")
    finally:
        cursor.close()
        conn.close()


# 데이터를 가져오고 처리하는 작업
def task():
    print("데이터를 가져오고 처리합니다...")
    today_matches = fetch_today_matches()
    team_names = fetch_team_names()
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(crawl_match_cheer, match, team_names) for match in today_matches]
        for future in futures:
            result = future.result()
            print(result)

            # 데이터베이스에 결과 삽입 또는 업데이트
            data = {
                'match_date': result['url'].split('/')[4][:8],  # URL에서 날짜를 추출
                'team1_code': result['url'].split('/')[4][8:10],  # URL에서 팀1 코드 추출
                'team2_code': result['url'].split('/')[4][10:12],  # URL에서 팀2 코드 추출
                'left_team_name': result['left_team_name'],
                'left_team_count': result['left_team_count'],
                'right_team_name': result['right_team_name'],
                'right_team_count': result['right_team_count'],
                'url': result['url']
            }
            upsert_match_cheer_stats(data)


# 스케줄러 설정
def run_scheduler():
    schedule.every(5).seconds.do(task)  # 30초마다 실행
    while True:
        schedule.run_pending()
        time.sleep(1)  # 1초 대기


if __name__ == "__main__":
    run_scheduler()
