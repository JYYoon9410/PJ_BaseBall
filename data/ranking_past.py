import cx_Oracle
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time

# Oracle DB 연결 함수
def get_oracle_connection():
    dsn_tns = cx_Oracle.makedsn('localhost', '1521', sid='xe')
    connection = cx_Oracle.connect(user='base_man', password='1111', dsn=dsn_tns)
    return connection

# Chrome 드라이버 설정 함수
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

# 특정 날짜에 대해 데이터 크롤링 함수
def crawl_and_store_data(target_date_str):
    driver = get_driver()
    driver.get('https://www.koreabaseball.com/Record/TeamRank/TeamRankDaily.aspx')

    try:
        # 날짜 이동 버튼 클릭 함수
        def navigate_to_date(date_str):
            current_date = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.ID, 'cphContents_cphContents_cphContents_lblSearchDateTitle'))
            ).text
            current_date = datetime.strptime(current_date, '%Y.%m.%d')
            target_date = datetime.strptime(date_str, '%Y-%m-%d')

            while current_date != target_date:
                if current_date > target_date:
                    prev_button = driver.find_element(By.CSS_SELECTOR,
                                                      '#cphContents_cphContents_cphContents_udpRecord > div.yeardate > span.date_prev > input')
                    prev_button.click()
                    time.sleep(1)  # 페이지 로딩 대기 (필요 시 조정 가능)
                elif current_date < target_date:
                    next_button = driver.find_element(By.CSS_SELECTOR,
                                                      '#cphContents_cphContents_cphContents_udpRecord > div.yeardate > span.date_next > input')
                    next_button.click()
                    time.sleep(1)  # 페이지 로딩 대기 (필요 시 조정 가능)

                current_date_str = driver.find_element(By.ID, 'cphContents_cphContents_cphContents_lblSearchDateTitle').text
                current_date = datetime.strptime(current_date_str, '%Y.%m.%d')

                # 월요일을 건너뛰기 위해 조정
                if current_date.weekday() == 0:  # 월요일이면 전날로 이동
                    current_date -= timedelta(days=1)

        # 날짜로 이동
        navigate_to_date(target_date_str)

        # 페이지 로딩 대기
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, 'table.tData'))
        )

        # 페이지 소스 가져오기
        page_source = driver.page_source

        # 데이터베이스 연결
        conn = get_oracle_connection()
        cursor = conn.cursor()

        # 테이블에 데이터 삽입
        def insert_team_rankings(data):
            cursor.execute('''
            INSERT INTO BASE_MAN.TEAM_RANKINGS (RANK, TEAM_NAME, GAMES, WINS, DRAWS, LOSSES, WIN_RATE, GAME_DIFF, RANK_DATE)
            VALUES (:rank, :team_name, :games, :wins, :draws, :losses, :win_rate, :game_diff, :rank_date)
            ''', data)

        # 페이지 데이터 추출 및 DB 삽입
        soup = BeautifulSoup(page_source, 'html.parser')

        table = soup.find('table', {'class': 'tData'})
        rows = table.find_all('tr')

        # 날짜를 `RANK_DATE`로 설정
        rank_date = datetime.strptime(target_date_str, '%Y-%m-%d').strftime('%Y-%m-%d')

        for row in rows[1:]:  # 첫 번째 행은 헤더이므로 제외
            cols = row.find_all('td')
            if len(cols) < 12:
                continue  # 데이터가 부족한 경우 건너뛰기

            data = {
                'rank': int(cols[0].text.strip()),
                'team_name': cols[1].text.strip(),
                'games': int(cols[2].text.strip()),
                'wins': int(cols[3].text.strip()),
                'draws': int(cols[5].text.strip()),
                'losses': int(cols[4].text.strip()),
                'win_rate': cols[6].text.strip(),
                'game_diff': cols[7].text.strip(),
                'rank_date': rank_date
            }

            # 데이터베이스에 저장
            insert_team_rankings(data)

        # 변경 사항 저장
        conn.commit()

        # 데이터베이스 연결 종료
        conn.close()

        # 브라우저 닫기
        driver.quit()

        # 데이터 삽입 완료 메시지 출력
        print(f"데이터 삽입 완료: {rank_date}")

    except Exception as e:
        print(f"오류 발생 ({target_date_str}): {e}")
        driver.quit()

# 날짜 범위 함수
def get_date_range(start_date, end_date):
    start = datetime.strptime(start_date, '%Y-%m-%d')
    end = datetime.strptime(end_date, '%Y-%m-%d')
    delta = end - start
    return [start + timedelta(days=i) for i in range(delta.days + 1)]

# 사용자가 지정한 날짜 범위
start_date = '2024-07-23'
end_date = '2024-07-28'
date_range = get_date_range(start_date, end_date)

# 날짜 범위에 대해 데이터 크롤링 및 저장
for date in date_range:
    crawl_and_store_data(date.strftime('%Y-%m-%d'))
