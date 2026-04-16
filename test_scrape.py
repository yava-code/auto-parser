import httpx
from bs4 import BeautifulSoup

text = httpx.get('https://www.autoscout24.com/lst', headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}).text
cards = BeautifulSoup(text, 'lxml').select('article[data-testid="list-item"]')
if cards:
    print(cards[0].prettify())
else:
    print("No cards found")
