import csv
import random
import time
import requests
from bs4 import BeautifulSoup
import cloudscraper
from urllib.parse import urlparse
import json

# Créer un scraper qui peut contourner Cloudflare
scraper = cloudscraper.create_scraper(
    browser={
        'browser': 'chrome',
        'platform': 'windows',
        'desktop': True
    }
)

# Headers plus complets pour simuler un vrai navigateur
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "DNT": "1",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
}

# Demander le fichier CSV à l'utilisateur
csv_path = input("Entrez le chemin vers le fichier CSV : ").strip()

# Lecture des liens depuis le CSV
with open(csv_path, newline='', encoding='utf-8') as f:
    reader = csv.reader(f)
    liens = [row[0] for row in reader if row]

# Limiter à 30 liens aléatoires si nécessaire
if len(liens) > 30:
    liens = random.sample(liens, 30)

print(f"{len(liens)} liens à traiter.")
print("Utilisation de cloudscraper pour contourner les protections anti-bot...")

# Liste pour stocker les résultats
resultats = []

# Fonction pour extraire les informations de contact
def extraire_infos_contact(soup, url):
    infos = {
        'url': url,
        'nom_magasin': '',
        'telephone': '',
        'adresse': '',
        'horaires': []
    }
    
    try:
        # Chercher le nom du magasin
        nom_elem = soup.find('h1')
        if nom_elem:
            infos['nom_magasin'] = nom_elem.get_text(strip=True)
        
        # Chercher le téléphone (plusieurs sélecteurs possibles)
        tel_selectors = [
            'a[href^="tel:"]',
            'span[itemprop="telephone"]',
            '.phone',
            '.telephone',
            'div:contains("Tél")',
            'div:contains("Téléphone")'
        ]
        
        for selector in tel_selectors:
            if selector.startswith('div:contains'):
                # Pour les sélecteurs contains, on doit chercher différemment
                divs = soup.find_all('div', string=lambda text: 'Tél' in text if text else False)
                for div in divs:
                    parent = div.parent
                    if parent:
                        text = parent.get_text(strip=True)
                        # Extraire le numéro de téléphone
                        import re
                        tel_match = re.search(r'[\d\s\.\-\(\)]+', text)
                        if tel_match and len(tel_match.group()) > 8:
                            infos['telephone'] = tel_match.group().strip()
                            break
            else:
                tel_elem = soup.select_one(selector)
                if tel_elem:
                    if tel_elem.name == 'a':
                        infos['telephone'] = tel_elem.get('href', '').replace('tel:', '')
                    else:
                        infos['telephone'] = tel_elem.get_text(strip=True)
                    break
        
        # Chercher l'adresse
        addr_selectors = [
            'address',
            '[itemprop="address"]',
            '.address',
            '.store-address',
            'div[class*="address"]'
        ]
        
        for selector in addr_selectors:
            addr_elem = soup.select_one(selector)
            if addr_elem:
                infos['adresse'] = addr_elem.get_text(strip=True).replace('\n', ', ')
                break
        
        # Chercher les horaires
        hours_selectors = [
            '.opening-hours',
            '.horaires',
            '[itemprop="openingHours"]',
            'div[class*="hours"]',
            'div[class*="horaire"]'
        ]
        
        for selector in hours_selectors:
            hours_elems = soup.select(selector)
            if hours_elems:
                for elem in hours_elems:
                    hour_text = elem.get_text(strip=True)
                    if hour_text:
                        infos['horaires'].append(hour_text)
                break
        
    except Exception as e:
        print(f"    Erreur lors de l'extraction : {e}")
    
    return infos

# Traitement des liens avec retry logic
max_retries = 3

for i, url in enumerate(liens, 1):
    print(f"\n[{i}/{len(liens)}] Récupération : {url}")
    
    success = False
    for retry in range(max_retries):
        try:
            # Attendre un peu plus longtemps entre les requêtes
            if retry > 0:
                wait_time = random.uniform(5, 10) * (retry + 1)
                print(f"  ⏳ Nouvelle tentative dans {wait_time:.1f} secondes...")
                time.sleep(wait_time)
            
            # Utiliser cloudscraper au lieu de requests
            response = scraper.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                # Parse HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extraire les informations
                infos = extraire_infos_contact(soup, url)
                resultats.append(infos)
                
                print(f"  ✅ Succès!")
                if infos['nom_magasin']:
                    print(f"    📍 Nom: {infos['nom_magasin']}")
                if infos['telephone']:
                    print(f"    📞 Tél: {infos['telephone']}")
                if infos['adresse']:
                    print(f"    🏠 Adresse: {infos['adresse'][:50]}...")
                
                success = True
                break
                
            elif response.status_code == 403:
                print(f"  ⚠ Erreur 403 - Tentative {retry + 1}/{max_retries}")
                if retry == max_retries - 1:
                    print(f"  ❌ Échec après {max_retries} tentatives")
                    resultats.append({'url': url, 'erreur': '403 Forbidden'})
            else:
                print(f"  ⚠ Code de statut: {response.status_code}")
                
        except Exception as e:
            print(f"  ⚠ Erreur : {str(e)[:100]}")
            if retry == max_retries - 1:
                resultats.append({'url': url, 'erreur': str(e)[:100]})
    
    # Pause aléatoire entre les requêtes (plus longue pour éviter la détection)
    if i < len(liens):
        pause = random.uniform(3, 7)
        print(f"  ⏸ Pause de {pause:.1f} secondes...")
        time.sleep(pause)

# Sauvegarder les résultats dans un fichier CSV
output_file = csv_path.replace('.csv', '_resultats.csv')
print(f"\n📝 Sauvegarde des résultats dans : {output_file}")

with open(output_file, 'w', newline='', encoding='utf-8') as f:
    fieldnames = ['url', 'nom_magasin', 'telephone', 'adresse', 'horaires', 'erreur']
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    
    for resultat in resultats:
        # Convertir la liste des horaires en string
        if 'horaires' in resultat and isinstance(resultat['horaires'], list):
            resultat['horaires'] = ' | '.join(resultat['horaires'])
        writer.writerow(resultat)

print(f"\n✅ Script terminé. {len(resultats)} résultats sauvegardés.")
print(f"   Fichier de sortie : {output_file}")
