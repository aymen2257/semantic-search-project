
import requests
import lxml.etree
import json
h = {"User-Agent": "Mozilla/5.0"}


urlsxml=['https://www.ooredoo.tn/Personal/1_en_0_sitemap.xml','https://www.ooredoo.tn/Personal/1_fr_0_sitemap.xml']

def extract_urls(url,timeout=30):
            response = requests.get(url, headers=h, timeout=timeout)
            response.raise_for_status()
            sitemap_tree = lxml.etree.fromstring(response.content)
            sitemap_urls = sitemap_tree.xpath("//ns:url/ns:loc/text()", namespaces={"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"})
            url_list=[u.strip() for u in sitemap_urls if u and u.strip()]
            return url_list

def turn_list_to_json(urls,FILE_PATH):
    with open(FILE_PATH, 'w' , encoding='utf-8') as f:
        json.dump(urls, f, ensure_ascii=False, indent=4)
    print(f"URLs saved to {FILE_PATH}")

urls_pers_en= extract_urls(urlsxml[0])
urls_pers_fr= extract_urls(urlsxml[1])
turn_list_to_json(urls_pers_en,'personal_urls_en.json')
turn_list_to_json(urls_pers_fr,'personal_urls_fr.json')
    
    

