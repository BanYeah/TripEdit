# TripEdit

## Dataset Download

```bash
dataset/
├── accommodation.csv
├── attraction.csv
├── cafe.csv
├── restaurant.csv
├── transport.csv
└── travel-time.csv
    # measured using a walking and public transit travel-time API based on the OSM and GTFS data in the route/
    # for November 11, 2026, at 11:00 AM
```
<br>

## Environment Setup

```bash
conda env create -f environment.yml
conda activate trip-edit

# conda env update -f environment.yml
```
<br>

## API

```bash
python app.py
```

- The development server runs at http://127.0.0.1:8000.
- API documentation is available at http://127.0.0.1:8000/docs.
