"""Canonical GRID schema description for LLM grounding."""

SCHEMA_FOR_LLM = """
## PostgreSQL schema (GTTAC GRID)

### incidents (VIEW over raw GRID data)
- incident_id TEXT PK — unique incident identifier
- incident_date DATE NOT NULL — full date; column is named "incident_date", NOT "date"
- year SMALLINT — pre-computed from incident_date; use for year filtering (e.g. WHERE i.year = 2022)
- month SMALLINT — pre-computed from incident_date; use for month filtering
- region TEXT — GTTAC regional classification (e.g. 'Western Asia', 'Sub-Saharan Africa', 'Southern Asia', 'Western Europe', 'Northern Africa', 'South America', 'Eastern Europe', 'Central Asia', 'East Asia', 'North America', 'Caribbean', 'Oceania')
- country TEXT — country name (e.g. 'IRAQ', 'NIGERIA', 'AFGHANISTAN')
- state_province TEXT, city TEXT
- latitude DOUBLE PRECISION, longitude DOUBLE PRECISION
- incident_type TEXT — always 'Terrorist Incident' in this dataset
- incident_summary TEXT

### perpetrators (VIEW — one row per ideology per incident; join on incident_id)
- incident_id TEXT FK → incidents(incident_id)
- ideology_category TEXT — one of: 'Religious/Jihad', 'Ethno-nationalist', 'Iran-linked', 'Left-wing', 'Right-wing', 'Cartel', 'Gang-related', 'Anarchist', 'Religious/Other', 'Single Issue', 'Vigilante', 'Unknown'
- group_name TEXT (always NULL — not available in this dataset)
- is_designated_fto BOOLEAN

### tactics (VIEW — one row per tactic per incident; join on incident_id)
- incident_id TEXT FK → incidents(incident_id)
- tactic_type TEXT — one of: 'Assassination', 'Civil Violence', 'Explosive/Bomb Attack', 'Armed Attack', 'Conspiracy/Covert Ops', 'Unknown'
- weapon_type TEXT — one of: 'Firearms', 'Explosives/IED', 'Incendiary', 'Improvised', 'Melee', 'Other', 'Unclear', NULL
- is_suicide_attack BOOLEAN

### casualties (VIEW — one row per incident; join on incident_id)
- incident_id TEXT FK → incidents(incident_id)
- killed_total INTEGER
- wounded_total INTEGER
- perpetrator_fatalities INTEGER
- target_type TEXT (always NULL — not available in this dataset)

### dashboard_summary_stats (VIEW)
- total_incidents BIGINT, total_casualties NUMERIC, most_affected_region TEXT

## Methodology rules
1. incidents.incident_type is always 'Terrorist Incident'; incident_type filter is valid but 'VITA' will return no rows.
2. "Total casualties" = SUM(casualties.killed_total + casualties.wounded_total).
3. One incident can have multiple perpetrators/tactics rows (one per active flag). Use COUNT(DISTINCT i.incident_id) when joining these tables.
4. incident_id is TEXT in all tables — join with: incidents i JOIN casualties c ON c.incident_id = i.incident_id.
5. Region values use GTTAC classification (region column on incidents). Country values are uppercase (e.g. 'IRAQ').
"""

ALLOWED_TABLES = frozenset(
    {"incidents", "perpetrators", "tactics", "casualties", "dashboard_summary_stats"}
)
