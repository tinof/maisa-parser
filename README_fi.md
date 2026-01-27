# Maisa Clinical Data Parser

[![CI](https://github.com/tinof/maisa-parser/actions/workflows/ci.yml/badge.svg)](https://github.com/tinof/maisa-parser/actions/workflows/ci.yml)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Python-työkalu, joka jäsentää ja yhdistää HL7 CDA (Clinical Document Architecture) XML -tiedostoja, jotka on viety **Maisa**-asiakasportaalista (**Apotti**-järjestelmän käytössä Suomessa).

Se poimii keskeiset terveystiedot rakenteiseen, koneluettavaan JSON-muotoon (`patient_history.json`).

---

## 🚨 TÄRKEÄ LÄÄKETIETEELLINEN VAROITUS

> [!CAUTION]
> **Tekoäly (LLM) EI ole lääkäri, sairaanhoitaja tai terveydenhuollon ammattilainen.**
>
> - Tekoälymallit ovat **tekstinennustusjärjestelmiä**, eivät lääketieteellisiä asiantuntijoita
> - Ne voivat antaa **virheellistä, vanhentunutta tai vaarallista tietoa**
> - Ne eivät tunne sinun yksilöllistä tilannettasi, historiaasi tai muita sairauksiasi
> - Tekoälyt ovat tunnettuja "hallusinoimaan" eli keksimään uskottavan kuuloisia mutta täysin vääriä vastauksia
>
> **Jos sinulla on terveyshuolia:**
> - Ota yhteyttä lääkäriin tai terveydenhuollon ammattilaiseen
> - Käytä virallisia terveyspalveluita (terveyskeskus, erikoissairaanhoito)
>
> **Tämä työkalu on tarkoitettu AINOASTAAN:**
> - Omien terveystietojen **varmuuskopiointiin** ja **järjestelyyn**
> - Tietojen **esikäsittelyyn** ennen lääkärikäyntiä (esim. "mitä laboratorioarvoja minulla on?")
> - **Tekniseen tutkimuskäyttöön** (data-analyysi, visualisointi)

---

## 🔐 Miten tämä työkalu suojaa yksityisyyttäsi

Tämä työkalu on suunniteltu **yksityisyys edellä** -periaatteella:

### Mitä työkalu tekee

| Ominaisuus | Kuvaus |
|------------|--------|
| 🏠 **Toimii täysin paikallisesti** | Kaikki käsittely tapahtuu omalla tietokoneellasi. Mitään dataa ei lähetetä mihinkään palvelimelle. |
| 🔒 **Oletuksena anonymisoitu** | Henkilötiedot (nimi, henkilötunnus, osoite, puhelin, sähköposti) poistetaan automaattisesti tulosteesta. |
| 📅 **Syntymäaika → ikä** | Tarkka syntymäpäivä muunnetaan iäksi, mikä riittää lääketieteelliseen kontekstiin. |
| 👨‍⚕️ **Hoitajien nimet piilotettu** | Lääkäreiden ja hoitajien nimet poistetaan tulosteesta. |
| ⚠️ **Selkeät varoitukset** | Työkalu varoittaa aina, jos tuloste sisältää arkaluonteista tietoa. |

### Mitä työkalu EI tee

| Ominaisuus | Kuvaus |
|------------|--------|
| ❌ **Ei lähetä dataa** | Työkalu ei koskaan ota yhteyttä internettiin. Voit tarkistaa tämän lähdekoodista. |
| ❌ **Ei tallenna dataa** | Työkalu ei tallenna mitään tietoja omiin tiedostoihinsa - vain sinun määrittelemääsi tulostetiedostoon. |
| ❌ **Ei kerää analytiikkaa** | Ei telemetriaa, ei lokitusta, ei seurantaa. |

### Lähdekoodin avoimuus

Koko lähdekoodi on avointa ja tarkastettavissa:
- **Pääjäsennin**: [`src/maisa_parser.py`](src/maisa_parser.py)
- **Tietosuojalogiikka**: [`src/privacy.py`](src/privacy.py)
- **Tietomallit**: [`src/models.py`](src/models.py)

Voit itse tarkistaa, mitä koodi tekee. Tämä on avoimen lähdekoodin etu.

---

## 🤔 Miksi oma jäsennin eikä valmis HL7-kirjasto?

Hyvä kysymys! HL7 CDA -standardille on olemassa valmiita kirjastoja, mutta:

### 1. CDA-standardi on valtava ja monimutkainen
HL7 CDA:n täydellinen rakennekuvaus sisältää **tuhansia sisäkkäisiä tietotyyppejä**. Täydellinen kirjasto olisi:
- Valtava kooltaan (megatavuja)
- Monimutkainen käyttää
- Joustamaton muutosten suhteen

### 2. Maisan data ei ole 100% standardin mukaista
Terveydenhuollon järjestelmät tulkitsevat standardeja eri tavoin. "Tiukka" kirjasto kaatuisi virheeseen, kun taas tämä skripti jatkaa toimintaansa.

### 3. Tarvitsemme vain osan datasta
Emme tarvitse koko CDA-standardia - vain Maisan käyttämät kentät. Kevyt, kohdennettu ratkaisu on helpompi ylläpitää.

### 4. Pydantic tuo tyyppiturvallisuuden
Käytämme silti **Pydantic**-tietomalleja, jotka tarjoavat:
- JSON-serialisoinnin
- Tyyppiturvallisuuden
- Validoinnin

Näin saamme kirjastojen edut ilman niiden haittoja.

---

## 🚀 Ominaisuudet

- **Yhdistetty potilashistoria**: Yhdistää tiedot useista `DOC*.XML`-tiedostoista yhdeksi kronologiseksi aikajanaksi.
- **Tekstimuotoinen poiminta**: Poimii älykkäästi vapaamuotoiset kliiniset merkinnät ("Päivittäismerkinnät", "Hoidon tarpeen arviointi") ja suodattaa pois toistuvat rakenteiset listat (lääkitys, laboratoriotulokset) vähentääkseen "kohinaa".
- **Rakenteisen tiedon jäsentäminen**:
  - **Potilasprofiili**: Henkilötiedot, yhteystiedot.
  - **Lääkitys**: Voimassa oleva lääkelista ja historia päivämäärineen ja annostuksineen.
  - **Laboratoriotulokset**: Testien nimet, arvot, yksiköt ja aikaleimat.
  - **Diagnoosit**: Aktiiviset ongelmat ICD-10/SNOMED-koodeilla (Ongelmalista-osiosta).
  - **Toimenpiteet**: Lääketieteelliset toimenpiteet kansallisilla koodeilla (lannepisto, ENMG, OCT jne.).
  - **Rokotukset**: Rokotustiedot ATC-koodeilla ja päivämäärillä.
  - **Sosiaalinen historia**: Tupakointitiedot, alkoholinkäyttö.
  - **Allergiat**: Tila ja aineet.
- **Kopioiden poisto**: Käsittelee päällekkäiset merkinnät useista dokumenteista.
- **Selkeä lopputulos**: Tuottaa siistin `patient_history.json`-tiedoston.
- **🛡️ Tietoturva ja Luotettavuus**: Käyttää **Pydantic**-tietomalleja datan validointiin. Jos XML-data ei vastaa odotettua rakennetta, jäsennin havaitsee virheen heti.

## 🛡️ Laadunvarmistus

Tämä projekti noudattaa ammattimaisia ohjelmistokehityksen standardeja:

- **Tyyppiturvallisuus**: Koodi on täysin tyypitetty ja tarkistettu `basedpyright`-työkalulla.
- **Validointi**: Tiukat tietomallit takaavat datan eheyden.
- **Tietoturva**: Automaattinen tietoturvaskannaus (`bandit`) haavoittuvuuksien havaitsemiseksi.
- **CI/CD**: Automaattinen testausputki varmistaa toimivuuden eri Python-versioilla.

## 🛠️ Esivaatimukset

- Python 3.8 tai uudempi
- [pipx](https://pipx.pypa.io/) (suositus) tai `pip`

## 📦 Asennus

### Suositus: pipx (eristetty asennus)

```bash
pipx install git+https://github.com/tinof/maisa-parser.git
```

Tämä asentaa `maisa-parser`-komennon globaalisti eristettyyn ympäristöön.

### Vaihtoehto: pip

```bash
pip install git+https://github.com/tinof/maisa-parser.git
```

### Kehitysasennus

```bash
git clone https://github.com/tinof/maisa-parser.git
cd maisa-parser
pip install -e ".[dev]"
```

## 📖 Käyttö

1. **Vie tiedot**: Lataa terveystietosi Maisasta ("Tilanneyhteenveto"). Kun olet purkanut ZIP-tiedoston, näet seuraavan kansion rakenteen:

    ```
    Tilanneyhteenveto_PP_Kuukausi_VVVV/
    ├── HTML/
    ├── IHE_XDM/
    │   └── <PotilasKansio>/     ← Tämä kansio sisältää XML-tiedostot!
    │       ├── DOC0001.XML
    │       ├── ...
    │       └── METADATA.XML
    ├── INDEX.HTM
    └── README.TXT
    ```

    > [!IMPORTANT]
    > Osoita jäsennin **`IHE_XDM/<PotilasKansio>/`** -hakemistoon, joka sisältää `DOC*.XML`-tiedostot. Älä osoita sitä puretun kansion juureen.

2. **Suorita jäsennin**:

    ```bash
    # Suorita oletusasetuksilla (redacted-tietosuojataso)
    maisa-parser /polku/kohteeseen/IHE_XDM/<PotilasKansio>/
    ```

    Esimerkiksi:

    ```bash
    maisa-parser ~/Downloads/Tilanneyhteenveto_16_joulu_2025/IHE_XDM/Ilias1/
    ```

3. **Tarkastele tulostetta**: Skripti luo `patient_history.json`-tiedoston nykyiseen työhakemistoosi.

## 🔐 Tietosuoja ja tietoturva

Tämä työkalu käsittelee **arkaluonteisia henkilökohtaisia terveystietoja**.
Oletuksena tuloste on **anonymisoitu** tietosuojariskien vähentämiseksi.

### Tietosuojatasot

| Taso | Komento | Käyttötarkoitus | Mitä poistetaan |
|------|---------|-----------------|-----------------|
| `strict` | `--privacy strict` | **Pilvi-LLM:t** (ChatGPT, Claude) | Kaikki henkilötiedot, hoitajien nimet, muistiinpanot, päivämäärät → vuosi-kuukausi |
| `redacted` | *(oletus)* | Jakaminen, tutkimus | Suorat tunnisteet, syntymäaika → ikä, hoitajien nimet |
| `full` | `--privacy full` | Henkilökohtainen varmuuskopio | Mitään ei poisteta ⚠️ |

### Kenttäkohtainen suojaus

| Kenttä | `strict` | `redacted` | `full` |
|--------|----------|------------|--------|
| Nimi | `[REDACTED]` | `[REDACTED]` | ✓ |
| Henkilötunnus | `[REDACTED]` | `[REDACTED]` | ✓ |
| Osoite | `[REDACTED]` | `[REDACTED]` | ✓ |
| Puhelin | `[REDACTED]` | `[REDACTED]` | ✓ |
| Sähköposti | `[REDACTED]` | `[REDACTED]` | ✓ |
| Syntymäaika | `[REDACTED]` | → `ikä: 40` | ✓ |
| Sukupuoli | ✓ | ✓ | ✓ |
| Hoitajan nimi | `[REDACTED]` | `[REDACTED]` | ✓ |
| Muistiinpanot | *(poistettu)* | ✓ + varoitus | ✓ |
| Päivämäärät | vuosi-kk | ✓ | ✓ |
| Lääketieteellinen data | ✓ | ✓ | ✓ |

> [!NOTE]
> Lääketieteellinen data (lääkitys, laboratoriotulokset, diagnoosit) säilytetään **kaikilla tasoilla**, koska se on työkalun päätarkoitus.

### Esimerkit

```bash
# Oletus (redacted) - turvallinen useimpiin jakotilanteisiin
maisa-parser /polku/dataan -o terveys.json

# Strict - turvallinen pilvi-LLM-lataukseen
maisa-parser /polku/dataan --privacy strict -o terveys.json

# Full - vain henkilökohtaiseen varmuuskopioon
maisa-parser /polku/dataan --privacy full -o terveys.json
```

---

## ⚠️ Tekoälyn käyttö terveystietojen kanssa

### Pilvipalvelut (ChatGPT, Claude, Gemini)

> [!WARNING]
> **Älä lataa terveystietojasi pilvi-tekoälypalveluihin kevyesti.**
>
> - Et voi tietää, mitä tiedoillasi tehdään
> - Palveluntarjoajat voivat käyttää dataasi mallien kouluttamiseen
> - Tiedot voivat vuotaa tai joutua vääriin käsiin
> - EU:n GDPR ei välttämättä suojaa, jos data siirtyy EU:n ulkopuolelle

**Jos silti haluat käyttää pilvipalveluita:**
1. Käytä **aina** `--privacy strict` -tilaa
2. Lue palvelun tietosuojaehdot
3. Harkitse, onko hyöty riskin arvoinen

### Paikalliset tekoälymallit (suositus)

Parempi vaihtoehto on käyttää **paikallisesti toimivaa tekoälyä**:

| Työkalu | Kuvaus | Linkki |
|---------|--------|--------|
| **Ollama** | Helppo tapa ajaa LLM:iä paikallisesti | [ollama.ai](https://ollama.ai) |
| **LM Studio** | Graafinen käyttöliittymä paikallisille malleille | [lmstudio.ai](https://lmstudio.ai) |
| **llama.cpp** | Kevyt C++-toteutus | [GitHub](https://github.com/ggerganov/llama.cpp) |

**Paikallisen mallin edut:**
- ✅ Data ei poistu tietokoneeltasi
- ✅ Ei tietosuojahuolia
- ✅ Toimii ilman internetyhteyttä
- ✅ Voit käyttää `--privacy full` -tilaa turvallisesti

**Esimerkki Ollaman kanssa:**
```bash
# 1. Luo terveystiedosto
maisa-parser /polku/dataan --privacy redacted -o terveys.json

# 2. Kysy paikalliselta mallilta
ollama run llama3.2 "Lue tämä JSON ja tee yhteenveto laboratoriotuloksista: $(cat terveys.json)"
```

---

### ⚠️ Tekoälypalveluiden varoitus

> **Ennen lataamista ChatGPT:hen, Claudeen tai muihin pilvipalveluihin:**
> - Käytä `--privacy strict` -tilaa
> - Vapaamuotoiset muistiinpanot voivat silti sisältää tunnistavia tietoja
> - Harkitse **paikallisen tekoälyn** käyttöä (Ollama, LM Studio)

### Maksimaalinen tietoturva

```bash
maisa-parser /polku/dataan --privacy strict -o terveys_turvallinen.json
```

### Paluukoodit

| Koodi | Merkitys |
|-------|----------|
| 0 | Onnistui |
| 1 | Tuntematon virhe |
| 2 | Virheelliset argumentit / polkua ei löydy |
| 3 | XML-jäsennysvirhe |
| 4 | Tietojen poimintavirhe |
| 5 | Tiedoston kirjoitusvirhe |

## 📂 Tulosteen rakenne

Luotu JSON sisältää:

```json
{
  "patient_profile": { ... },
  "clinical_summary": {
    "allergies": [ ... ],
    "active_medications": [ ... ],
    "medication_history": [ ... ]
  },
  "lab_results": [ ... ],
  "diagnoses": [ ... ],
  "encounters": [
    {
      "date": "2024-10-10T12:00:00",
      "type": "Hoito- ja palveluyhteenveto",
      "provider": "Lääkärin Nimi",
      "notes": "Käynnin vapaamuotoinen teksti...",
      "source_file": "DOC0018.XML"
    },
    ...
  ]
}
```

## ⚠️ Tärkeä huomautus yksityisyydestä

Tämä työkalu käsittelee **arkaluonteisia terveystietoja**.

- **Älä vie (commit)** XML-tietojasi tai luotua JSON-tulostetta GitHubiin tai mihinkään julkiseen repositorioon.
- Mukana on `.gitignore`-tiedosto, joka auttaa estämään `.XML` ja `.json` -tiedostojen vahingossa tapahtuvan viennin.
- Käsittele terveystietojasi aina huolellisesti.

## 📥 Kuinka viedä tietosi Maisasta

1. Kirjaudu sisään osoitteessa **[Maisa.fi](https://www.maisa.fi)**.
2. Mene valikkoon **Valikko** > **Tietojen jakaminen ja lataaminen** > **Lataa tilannekatsaus**.
3. Valitse **"Lataa kaikki"** (tai vain haluamasi tiedot).
4. Lataa ZIP-tiedosto ja pura se.
5. Etsi puretusta paketista kansio `IHE_XDM`, joka sisältää `DOC*.XML`-tiedostot.

## ⚠️ Vastuuvapauslauseke

> [!IMPORTANT]
> **Tämä ohjelmisto on tarkoitettu AINOASTAAN opetus- ja tiedotustarkoituksiin.**
>
> - Se **EI ole lääkinnällinen laite** eikä sitä ole tarkoitettu diagnosointiin tai hoitoon
> - **Älä tee hoitopäätöksiä** tämän työkalun tulosten perusteella
> - Konsultoi **aina** terveydenhuollon ammattilaista lääketieteellisissä kysymyksissä
> - Tekijät eivät ole vastuussa jäsennys- tai tulkintavirheistä

Käyttämällä tätä työkalua hyväksyt, että olet itse vastuussa omien terveystietojesi suojaamisesta ja tulkinnasta.

---

## 🤝 Osallistuminen

Voit vapaasti lähettää virheraportteja (issues) tai pull request -pyyntöjä, jos löydät virheitä tai haluat parantaa jäsennyslogiikkaa erityyppisille Maisa-dokumenteille.

## 📄 Lisenssi

Tämä projekti on lisensoitu MIT-lisenssillä. Katso [LICENSE](LICENSE)-tiedosto lisätietoja varten.
