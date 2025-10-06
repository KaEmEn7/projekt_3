"""
main.py: třetí projekt do Engeto Online Python Akademie

author: Kamil Mach
email: kamil.machuj@gmail.com
"""

import re
import requests
from bs4 import BeautifulSoup as bs
from requests import get
import random
import csv
from urllib.parse import urlparse, parse_qs
import sys


#konstanta:
base_url = "https://www.volby.cz/pls/ps2017nss/"

def nacti_html(url):
    """Načte HTML obsah z dané URL."""
    odpoved = requests.get(url)
    return bs(odpoved.text, features="html.parser")

def najdi_tabulky(rozdelene_html):
    """Najde obě tabulky s výsledky."""
    tabulka_1 = rozdelene_html.select_one("div:nth-of-type(2) > div > div:nth-of-type(1) > table")  # Hledá tabulku s výsledky
    tabulka_2 = rozdelene_html.select_one("div:nth-of-type(2) > div > div:nth-of-type(2) > table")
    
    return tabulka_1, tabulka_2

def zpracuj_tabulku(tabulka, strany, hlasy):
    """Zpracuje tabulku a přidá názvy stran do seznamu."""

    if tabulka:
        radky = tabulka.select("tr:nth-of-type(n+3)")  # Začínám od třetího řádku
        for radek in radky:
            bunky = radek.find_all("td")
            if len(bunky) >= 3:  # Zkontroluje, zda řádek obsahuje alespoň tři buňky
                nazev_strany = bunky[1].text.strip()
                nazev_strany = nazev_strany.replace('"', '').replace(',', '_').strip()  # Odstranění speciálních znaků
                hlasy_text = bunky[2].text.strip()  # Text s počtem hlasů
                hlasy_text = re.sub(r"[^\d]", "", hlasy_text)  # Odstraní nečíselné znaky
                hlasy_strany = int(hlasy_text) if hlasy_text else 0  # Převod na číslo nebo 0

                # ladicí výpis
                #print(f"Nalezen název strany: {nazev_strany}")
                # Přidání názvu strany a hlasů
                if nazev_strany and nazev_strany != "-" and nazev_strany not in strany:
                    strany.append(nazev_strany)
                if nazev_strany in hlasy:
                    hlasy[nazev_strany] += hlasy_strany  # Přičítá hlasy

def inicializuj_hlasy(strany):
    """Inicializuje slovník s hlasy pro každou stranu."""
    return {strana.replace('"', '').replace(',', '_').strip(): 0 for strana in strany}

def zapis_hlavicku_csv(vystupni_soubor, strany):
    """Zapíše hlavičku do CSV souboru."""
    with open(vystupni_soubor, "w", encoding="utf-8", newline="") as csvfile:
        csv_writer = csv.writer(csvfile)
        csv_writer.writerow(["code", "location", "registered", "envelopes", "valid"] + strany)
    return vystupni_soubor


def nacti_stranku_obce(obec_odkaz, base_url):
    """Načte stránku obce a vrátí rozparsovaný HTML obsah."""
    obec_url = base_url + obec_odkaz
    odpoved = requests.get(obec_url)
    return bs(odpoved.text, features="html.parser"), obec_url


def ziskej_zakladni_udaje(rozdelene_html, obec_url):
    """Získá základní údaje o obci (code, location, registered, envelopes, valid)."""
    # Extrakce hodnoty `xobec` z URL
    parsed_url = urlparse(obec_url)
    query_params = parse_qs(parsed_url.query)
    code = query_params.get("xobec", [""])[0]  # Získání hodnoty `xobec`

    # Najde hodnotu `location`
    location_element = rozdelene_html.select_one("h3:nth-of-type(3)")
    location = location_element.text.strip().replace("Obec: ", "") if location_element else "Neznámá obec"

    # Získání hodnoty `registered`, `envelopes`, `valid` z tabulky
    tabulka_1 = rozdelene_html.select_one("#ps311_t1")
    try:
        registered = re.sub(r"[^\d]", "", tabulka_1.select_one("tr:nth-child(3) > td:nth-child(4)").text.strip())
    except AttributeError:
        registered = "0"

    try:
        envelopes = re.sub(r"[^\d]", "", tabulka_1.select_one("tr:nth-of-type(3) td:nth-of-type(5)").text.strip())
    except AttributeError:
        envelopes = "0"

    try:
        valid = re.sub(r"[^\d]", "", tabulka_1.select_one("tr:nth-of-type(3) td:nth-of-type(8)").text.strip())
    except AttributeError:
        valid = "0"

    return code, location, registered, envelopes, valid


def zpracuj_hlasy(rozdelene_html, strany):
    """Zpracuje tabulky s hlasy a vrátí slovník s hlasy pro každou stranu."""
    tabulka_hlasy_1 = rozdelene_html.select_one("#inner > div:nth-child(1)")
    tabulka_hlasy_2 = rozdelene_html.select_one("#inner > div:nth-child(2)")
    tabulky = [tabulka_hlasy_1, tabulka_hlasy_2]

    hlasy = {strana: 0 for strana in strany}

    for tabulka in tabulky:
        if tabulka:  # Zkontroluje, zda tabulka existuje
            radky = tabulka.select("tr:nth-of-type(n+3)")  # Začínáme od třetího řádku (kde jsou strany)
            for radek in radky:
                bunky = radek.find_all("td")
                if len(bunky) >= 3:  # Zkontroluje, zda řádek obsahuje alespoň tři buňky
                    nazev_strany = bunky[1].text.strip()
                    hlasy_text = bunky[2].text.strip()
                    hlasy_text = re.sub(r"[^\d]", "", hlasy_text)  # Odstraní nečíselné znaky
                    hlasy_strany = int(hlasy_text) if hlasy_text else 0
                    if nazev_strany in hlasy:
                        hlasy[nazev_strany] += hlasy_strany  # Přičítá hlasy

    return hlasy


def scrapuj_vysledky_obce(obec_odkaz, csv_writer, strany):
    """Scrapuje výsledky pro jednu obec a zapíše je do CSV."""
    rozdelene_html, obec_url = nacti_stranku_obce(obec_odkaz, base_url)

    # Získání základních údajů
    code, location, registered, envelopes, valid = ziskej_zakladni_udaje(rozdelene_html, obec_url)

    # Zpracování hlasů
    hlasy = zpracuj_hlasy(rozdelene_html, strany)

    # Připravte řádek pro CSV
    row = [code, location, registered, envelopes, valid] + [hlasy[strana] for strana in strany]
    csv_writer.writerow(row)  # Zápis do CSV
    # ladicí výpis
    #print(row)  # Výpis pro kontrolu


def main(odkaz, vystupni_soubor):
    """Hlavní funkce programu."""
    # Načtení stránky územního celku
    rozdelene_html = nacti_html(odkaz)

    # Najděte odkazy na obce
    obce = []
    tr_elementy = rozdelene_html.find_all("tr")
    for tr in tr_elementy:
        td_elementy = tr.find_all("td")
        if td_elementy:
            a_tag = td_elementy[0].find("a", href=True)
            if a_tag and not a_tag["href"].endswith("xjazyk=CZ"):
                obce.append(a_tag["href"])
    # ladidi výpis
    #print("Počet obcí:", len(obce))

    #získání seznamu stran z první obce
    prvni_obec_url = obce[0]
    rozdelene_html, obec_url = nacti_stranku_obce(prvni_obec_url, base_url)

    # Najdu obě tabulky
    tabulka_1, tabulka_2 = najdi_tabulky(rozdelene_html)

    #inicializace seznamu stran
    strany = []

    # Zpracování tabulek a získání seznamu stran
    zpracuj_tabulku(tabulka_1, strany, {})
    zpracuj_tabulku(tabulka_2, strany, {})

    #ladící výpis
    #print("Seznam stran:", strany, "počet stran:", len(strany))

    # otevření výstupního souboru pro zápis výsledků
    with open(vystupni_soubor, "w", encoding="utf-8", newline="") as csvfile:
        csv_writer = csv.writer(csvfile)
        # Zápis hlavičky do CSV
        csv_writer.writerow(["code", "location", "registered", "envelopes", "valid"] + strany)

        # Scrapování výsledků pro každou obec
        for obec in obce:
            scrapuj_vysledky_obce(obec, csv_writer, strany)

    print(f"Výsledky byly uloženy do souboru: {vystupni_soubor}")

if __name__ == "__main__":
    # kontrola dvou argumentů
    if len(sys.argv) != 3:
        sys.exit(1)

    # Získání argumentů z příkazové řádky
    odkaz = sys.argv[1]
    vystupni_soubor = sys.argv[2]

    # Spuštění funkce main s argumenty
    main(odkaz, vystupni_soubor)