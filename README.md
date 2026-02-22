# IOF Orienteering Ranking Data

This repository hosts [IOF (International Orienteering Federation)](https://orienteering.sport/) World Ranking data in JSON format.

## Purpose

- Provides IOF World Ranking data for use by the **JOY Start List Generator WebUI** and other orienteering tools
- Data is fetched directly from the public IOF API and stored here for easy access
- Enables client-side applications to fetch ranking data without CORS restrictions

## Data Format

Ranking data is stored in the `data/` directory in JSON format, organized by discipline and category.

## Data Source

All data is sourced from the official [IOF World Ranking](https://ranking.orienteering.sport/) public API.

## Updates

Data is updated periodically via `fetch-ranking.py`.

## License

The ranking data is publicly available from IOF. This repository merely mirrors it in a convenient format.
