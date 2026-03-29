# Bidrag til OpenSAK

Tak for din interesse i at bidrage! Her er hvordan du kommer i gang.

## Rapporter fejl

Brug [GitHub Issues](https://github.com/AgreeDK/opensak/issues) og inkludér:
- Platform og version (f.eks. "Linux Mint 21.3")
- Python version (`python3 --version`)
- Hvad du forsøgte at gøre
- Fejlbesked fra terminalen

## Foreslå nye features

Åbn et GitHub Issue med labelen "enhancement" og beskriv hvad du gerne vil have og hvorfor.

## Bidrag med kode

1. Fork projektet
2. Opret en branch: `git checkout -b feature/min-feature`
3. Kør tests: `pytest -v tests/`
4. Commit: `git commit -m "Tilføj: beskrivelse"`
5. Push: `git push origin feature/min-feature`
6. Åbn en Pull Request

## Opsætning til udvikling

```bash
git clone https://github.com/AgreeDK/opensak.git
cd opensak
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -v tests/   # kør tests
python run.py      # start programmet
```

## Sprogfiler

Vil du oversætte OpenSAK til et nyt sprog?
- Kopier `src/opensak/lang/da.py` til f.eks. `en.py`
- Oversæt alle strenge
- Åbn et Pull Request

*(Sprogfilsystemet er under udvikling)*
