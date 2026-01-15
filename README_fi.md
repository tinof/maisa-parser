# Maisa Clinical Data Parser

[![CI](https://github.com/tinof/maisa-parser/actions/workflows/ci.yml/badge.svg)](https://github.com/tinof/maisa-parser/actions/workflows/ci.yml)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

Python-työkalu, joka jäsentää ja yhdistää HL7 CDA (Clinical Document Architecture) XML -tiedostoja, jotka on viety **Maisa**-asiakasportaalista (**Apotti**-järjestelmän käytössä Suomessa).

Se poimii keskeiset terveystiedot rakenteiseen, koneluettavaan JSON-muotoon (`patient_history.json`).

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

- **Tyyppiturvallisuus**: Koodi on täysin tyypitetty ja tarkistettu `mypy`-työkalulla.
- **Validointi**: Tiukat tietomallit takaavat datan eheyden.
- **Tietoturva**: Automaattinen tietoturvaskannaus (`bandit`) haavoittuvuuksien havaitsemiseksi.
- **CI/CD**: Automaattinen testausputki varmistaa toimivuuden eri Python-versioilla.

## 🛠️ Esivaatimukset

- Python 3.8 tai uudempi
- `pip` (Python-pakettien hallinta)

## 📦 Asennus

1. Kloonaa tämä repositorio tai lataa skripti.
2. Asenna tarvittavat riippuvuudet:

    ```bash
    pip install -r requirements.txt
    ```

    *(Pääasiallinen riippuvuus on `lxml` tehokasta XML-jäsennystä varten)*

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
    python src/maisa_parser.py /polku/kohteeseen/IHE_XDM/<PotilasKansio>/
    ```

    Esimerkiksi:

    ```bash
    python src/maisa_parser.py ~/Downloads/Tilanneyhteenveto_16_joulu_2025/IHE_XDM/Ilias1/
    ```

    Jos suoritat skriptin datakansion sisältä, et tarvitse argumentteja:

    ```bash
    cd ~/Downloads/Tilanneyhteenveto_16_joulu_2025/IHE_XDM/Ilias1/
    python /polku/kohteeseen/maisa-parser/src/maisa_parser.py
    ```

3. **Tarkastele tulostetta**: Skripti luo `patient_history.json`-tiedoston nykyiseen työhakemistoosi.

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

Käyttämällä tätä työkalua hyväksyt, että olet itse vastuussa omien terveystietojesi suojaamisesta.

## 🤝 Osallistuminen

Voit vapaasti lähettää virheraportteja (issues) tai pull request -pyyntöjä, jos löydät virheitä tai haluat parantaa jäsennyslogiikkaa erityyppisille Maisa-dokumenteille.

## 📄 Lisenssi

Tämä projekti on lisensoitu MIT-lisenssillä. Katso [LICENSE](LICENSE)-tiedosto lisätietoja varten.
