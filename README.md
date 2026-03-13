# flitex-overflightcharges

Python 3.13 + FastAPI microservice for calculating overflight charges based on FIR crossings and country-specific formulas.

## Overview

This service calculates overflight charges for flight routes by:
- Managing FIR (Flight Information Region) boundary data
- Maintaining country-specific charge formulas with version history
- Parsing ICAO route strings and detecting FIR crossings
- Calculating charges based on aircraft weight and distance
- Providing audit trails for compliance

## Technology Stack

- **Runtime**: Python 3.13
- **Web Framework**: FastAPI + Uvicorn
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Migrations**: Alembic
- **Testing**: pytest + hypothesis (property-based testing)
- **Containerization**: Docker + Docker Compose

## Getting Started

Documentation for setup, configuration, and API usage will be added as the service is developed.

## License

MIT License
