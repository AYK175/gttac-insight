# GTTAC GRID Data Dictionary (NL→SQL Mapping Context)

This document maps analyst terminology to the variables and join logic found in the GTTAC Record of Incident Database (GRID) 2023.

## 1. Core Metrics & Aggregations
* **Total Fatalities**: `SUM(num_killed)` (Includes both victims and perpetrators).
* **Total Injuries**: `SUM(num_wounded)`.
* **Total Victims Killed**: `SUM(num_killed - num_killed_perp)`.
* **Total Victims Wounded**: `SUM(num_wounded - num_wounded_perp)`.
* **U.S. Fatalities**: `SUM(num_killed_us)`.
* **U.S. Injuries**: `SUM(num_wounded_us)`.
* **Total Hostages/Kidnapped**: `SUM(num_hostkid)`.
* **Total U.S. Hostages/Kidnapped**: `SUM(num_hostkid_us)`.
* **Total Incidents**: `COUNT(DISTINCT unique_incident_id)`.

## 2. Geography ("Area")
* **Region**: `region_txt` (Name) or `region` (GENC Code).
* **Country**: `country_genc_txt` (Name) or `country_genc` (GENC Code).
* **State/Province**: `stateprovince_genc_txt`, `stateprovince_genc`, or `stateprovince_nongenc`.
* **City**: `city`.
* **Multi-location Incident**: `is_multi_location = 1`.

## 3. Temporal Variables ("Time")
* **Incident Date**: `incident_date` (dd/mm/yyyy).
* **Year**: `incident_year`.
* **Month**: `incident_month`.
* **Day**: `incident_day`.

## 4. Perpetrators & Ideology
* **Perpetrator Name**: `perp_name` (Available in Perpetrator File).
* **Perpetrator Code**: `perp_cd`.
* **Claim of Responsibility**: `claimed = 1`.
* **Ideology Flags (Incident File)**:
    * **Jihadist**: `ICat_Rjih = 1`
    * **Right-Wing**: `ICat_Right = 1`
    * **Left-Wing**: `ICat_Left = 1`
    * **Ethnonationalist/Separatist**: `ICat_Ethn = 1`
    * **Iranian-Backed**: `ICat_Iran = 1`
    * **Anarchist**: `ICat_ANA = 1`
    * **Religious (Other)**: `ICat_Rhbjc = 1`
    * **Vigilante**: `ICat_Vig = 1`

## 5. Tactics & Flags
* **Suicide Attack**: `is_suicide = 1`.
* **IED Used**: `is_ied = 1`.
* **Assassination**: `is_assassination = 1`.
* **Attack Drawing from Multiple Sources**: `is_multi_source_corr = 1`.

## 6. Weapons (Level 1 Categories)
* **Firearms**: `weapon_lvl1_fi = 1`
* **IED**: `weapon_lvl1_im = 1`
* **Explosives**: `weapon_lvl1_ex = 1`
* **UAV (Drone)**: `weapon_lvl1_ua = 1`
* **Incendiary**: `weapon_lvl1_in = 1`
* **Melee**: `weapon_lvl1_ml = 1`

## 7. Victims (Level 1 Categories)
*Variables exist for both Actual (`victim_lvl1_`) and Intended (`intended_victim_lvl1_`).*
* **Government**: `_go`
* **Military**: `_mi`
* **Police/Law Enforcement**: `_po` (Note: Level 2 `_go_07` is specific Law Enforcement).
* **Professions**: `_pr`
* **General Population**: `_gp`
* **Societal Groups**: `_ci`

## 8. Facilities (Level 1 Categories)
* **Commercial**: `facility_lvl1_co`
* **Government**: `facility_lvl1_go`
* **Infrastructure**: `facility_lvl1_in`
* **Military**: `facility_lvl1_mi`
* **Cultural/Religious**: `facility_lvl1_cu`

## 9. Join & Deduplication Rules
* **Primary Key**: `unique_incident_id` (9-digit).
* **Multi-incident Events**: Group by `incident_id` (7-digit); individual incidents are ordered by `incident_seq`.
* **Join Logic**:
    * **Incident to Perpetrator**: Join on `unique_incident_id`.
    * **Incident to Source**: Join on `unique_incident_id`.
* **Counting Rule**: Always use `COUNT(DISTINCT unique_incident_id)` when joining to Perpetrator or Source files to avoid over-counting incidents.
