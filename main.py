from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import requests
from bs4 import BeautifulSoup
from typing import List, Optional
import re
from urllib.parse import urljoin
import logging
from requests.exceptions import RequestException

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScrapingResponse(BaseModel):
    url: str
    page_title: Optional[str]
    titles: List[str]
    links: List[str]
    images: List[str]
    paragraphs: List[str]
    status: str
    error: Optional[str] = None

app = FastAPI(
    title="Advanced Web Scraper API",
    description="A modern web scraping API with multiple data extraction options",
    version="2.0.0"
)

# Configure CORS with more specific settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Mount static files with explicit HTML type
app.mount("/static", StaticFiles(directory="static", html=True), name="static")

def clean_text(text: str) -> str:
    """Clean and normalize text content."""
    return re.sub(r'\s+', ' ', text.strip())

def extract_content(soup: BeautifulSoup, base_url: str) -> dict:
    """Extract various types of content from the webpage."""
    try:
        page_title = soup.title.string if soup.title else None
        
        # Extract all headings
        titles = [clean_text(heading.get_text()) 
                 for heading in soup.find_all(['h1', 'h2', 'h3'])
                 if clean_text(heading.get_text())]

        # Extract links with better error handling
        links = []
        for link in soup.find_all('a', href=True):
            try:
                href = link['href']
                if href.startswith(('http://', 'https://')):
                    links.append(href)
                elif not href.startswith('#'):
                    links.append(urljoin(base_url, href))
            except Exception as e:
                logger.warning(f"Error processing link: {e}")
                continue

        # Extract images with error handling
        images = []
        for img in soup.find_all('img', src=True):
            try:
                src = img['src']
                if src.startswith(('http://', 'https://')):
                    images.append(src)
                else:
                    images.append(urljoin(base_url, src))
            except Exception as e:
                logger.warning(f"Error processing image: {e}")
                continue

        # Extract paragraphs
        paragraphs = [clean_text(p.get_text()) 
                     for p in soup.find_all('p')
                     if clean_text(p.get_text()) and len(clean_text(p.get_text())) > 50]

        return {
            "page_title": page_title,
            "titles": titles[:10],
            "links": links[:20],
            "images": images[:10],
            "paragraphs": paragraphs[:5]
        }

    except Exception as e:
        logger.error(f"Content extraction failed: {str(e)}")
        raise Exception(f"Content extraction failed: {str(e)}")

@app.get("/", response_class=HTMLResponse)
async def home():
    try:
        with open("static/index.html") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="index.html not found")

@app.get("/scrape", response_model=ScrapingResponse)
async def scrape_website(url: HttpUrl):
    logger.info(f"Attempting to scrape URL: {url}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Connection': 'keep-alive',
        }
        
        # Improved error handling for the request
        try:
            response = requests.get(
                str(url), 
                headers=headers, 
                timeout=10,
                verify=True  # Enable SSL verification
            )
            response.raise_for_status()
        except RequestException as e:
            logger.error(f"Request failed: {str(e)}")
            return ScrapingResponse(
                url=str(url),
                status="error",
                error=f"Failed to fetch URL: {str(e)}",
                page_title=None,
                titles=[],
                links=[],
                images=[],
                paragraphs=[]
            )

        # Parse content
        soup = BeautifulSoup(response.content, "html.parser")
        content = extract_content(soup, str(url))
        
        return ScrapingResponse(
            url=str(url),
            status="success",
            **content
        )

    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}")
        return ScrapingResponse(
            url=str(url),
            status="error",
            error=f"Scraping failed: {str(e)}",
            page_title=None,
            titles=[],
            links=[],
            images=[],
            paragraphs=[]
        )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "2.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
