from googleapiclient.discovery import build
from datetime import datetime, timedelta
import cx_Oracle

API_KEY = 'AIzaSyCCeIbocKAEeYfJi7RXXSUaiXhfF5wlUGw'
YOUTUBE_API_SERVICE_NAME = 'youtube'
YOUTUBE_API_VERSION = 'v3'

def get_oracle_connection():
    dsn_tns = cx_Oracle.makedsn('localhost', '1521', sid='xe')
    connection = cx_Oracle.connect(user='base_man', password='1111', dsn=dsn_tns)
    return connection

def get_youtube_videos(search_query, published_after, published_before, max_results=10):
    youtube = build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, developerKey=API_KEY)
    search_response = youtube.search().list(
        q=search_query,
        publishedAfter=published_after,
        publishedBefore=published_before,
        part='snippet',
        type='video',
        order='date',
        maxResults=max_results
    ).execute()

    videos = []
    for item in search_response.get('items', []):
        video_id = item['id']['videoId']
        title = item['snippet']['title']
        thumbnail_url = item['snippet']['thumbnails']['high']['url']
        video_url = f"https://youtu.be/{video_id}"
        published_date = item['snippet']['publishedAt']

        # 제목에 특정 문자열이 포함된 경우만 필터링
        if '[KBO 하이라이트]' in title:
            videos.append({
                'title': title,
                'thumbnail_url': thumbnail_url,
                'video_url': video_url,
                'published_date': published_date
            })

    return videos

def insert_video_to_db(video):
    connection = get_oracle_connection()
    cursor = connection.cursor()
    try:
        sql = """
            INSERT INTO HL_videos (title, thumbnail_url, video_url, upload_date)
            VALUES (:title, :thumbnail_url, :video_url, :upload_date)
        """
        cursor.execute(sql, {
            'title': video['title'],
            'thumbnail_url': video['thumbnail_url'],
            'video_url': video['video_url'],
            'upload_date': datetime.strptime(video['published_date'], '%Y-%m-%dT%H:%M:%SZ')
        })
        connection.commit()
    except cx_Oracle.DatabaseError as e:
        print(f"Database error: {e}")
    finally:
        cursor.close()
        connection.close()

def print_videos(videos):
    for video in videos:
        print(f"Title: {video['title']}")
        print(f"Thumbnail URL: {video['thumbnail_url']}")
        print(f"Video URL: {video['video_url']}")
        print(f"Published Date: {video['published_date']}")
        print()

# 사용자 지정 날짜 및 비디오 수
start_date = '2024-09-04T00:00:00Z'
end_date = '2024-09-05T23:59:59Z'
max_results = 50  # 최대 비디오 수

# 비디오 검색 및 데이터베이스에 저장
videos = get_youtube_videos('#KBO #KBO리그', start_date, end_date, max_results)
for video in videos:
    insert_video_to_db(video)
print_videos(videos)
