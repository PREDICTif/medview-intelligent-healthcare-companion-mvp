from diabetes_scraper_scheduler import incremental_diabetes_scraper
import os
from dotenv import load_dotenv

load_dotenv()

tavily_api_key = os.getenv('TAVILY_API_KEY')
bucket_name = os.getenv('S3_BUCKET_NAME')
print(f"Tavily API Key: {tavily_api_key}")
print(f"S3 Bucket: {bucket_name}")

# Smart incremental scraping - only new/updated content
response = incremental_diabetes_scraper(
    f"Run incremental scrape for diabetes content and store new findings in S3 bucket '{bucket_name}'"
)
print(response)