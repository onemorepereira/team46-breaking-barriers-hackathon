# Hazard and Exposure Sources: Catalog

**Roadmap:** H1 ([spec](spec.md)) · **Checked:** 2026-11-05 · **Status:** research record, not yet a registry

## Why this list exists
It records the sources an agent could use to answer a site-risk question, with what each licence allows. Examples:
- "Should we build housing, a solar farm, a wind farm or a school in this municipality?"
- "Is the risk of natural or man-made disasters there too high?"

It starts from a list the user researched, and adds sources for developing Asia-Pacific, ADB's region **[team]**. Every licence was checked on the publisher's page on 2026-11-05 **[ext]**. Two marks qualify that:
- **†:** the licence was read from a search summary of the official page, because the page itself didn't load. Re-check these before relying on them.
- **Correction:** the finding differs from the user's original list. The reasons are in [Corrections](#corrections-to-the-original-list).

**What "Commercial" means here:** whether ADB, a developer or LGND may use the data in work that is paid for or published. It isn't legal advice. [H1](spec.md) turns this page into a registry that the harness enforces, and ADB legal has the final word (report Table 1, §7.4) **[ext]**.

**Licence families:**
- **Clean:** public domain, CC0, CC BY, CC BY IGO, CDLA-Permissive. These allow commercial use with attribution.
- **Share-alike:** ODbL, CC BY-SA. Commercial use is allowed, but a database derived from the data must be released under the same licence. The repo holds none of it (`references/README.md`).
- **Non-commercial:** CC BY-NC, or a paid licence. Not usable for ADB outputs.
- **Unclear:** no licence found.

## Cyclone and wind
| Source | Publisher | What it gives | Coverage | Licence | Commercial | Checked at |
|---|---|---|---|---|---|---|
| IBTrACS v04r01 | NOAA NCEI | Historical tropical-cyclone tracks, 1842 to present | Global, 6 basins | "Full and open access" (WDC-Meteorology); WMO Res. 40 for commercial use. **Correction** | Yes (US federal; cite the DOI) | [ncei.noaa.gov](https://www.ncei.noaa.gov/products/international-best-track-archive) |
| STORM synthetic tracks, present day and 2015–2050 climate | Bloemendaal et al., 4TU | 10,000 synthetic years of tracks; the climate set uses SSP5-8.5 and 4 GCMs | Global cyclone basins | CC0. **Correction** | Yes | [4TU climate tracks](https://data.4tu.nl/articles/_/14237678/1); [4TU present tracks](https://data.4tu.nl/articles/_/12706085/3) † |
| STORM wind-speed return periods | Bloemendaal et al.; GeoTIFFs by Russell | Wind speed per return period, present and 2050 | Global, 10 km | CC0. **Correction** | Yes | [Zenodo GeoTIFFs](https://zenodo.org/records/7438145); [4TU](https://data.4tu.nl/datasets/0ea98bdd-5772-4da8-ae97-99735e891aff/1) † |
| Global Wind Atlas | DTU / World Bank ESMAP | Wind resource: speed and power density | Global, about 250 m | CC BY 4.0 | Yes | [World Bank catalogue](https://datacatalog.worldbank.org/search/dataset/0038957) † |
| Global Solar Atlas | World Bank ESMAP / Solargis | Solar irradiance (GHI, DNI) and PV output | Global, about 250 m | CC BY 4.0, plus a "mandatory and binding addition" whose text wasn't seen | With conditions | [World Bank catalogue](https://datacatalog.worldbank.org/search/dataset/0038509) † |

The two atlases measure resource quality, not hazard. A solar or wind siting answer needs both.

## Flood
| Source | Publisher | What it gives | Coverage | Licence | Commercial | Checked at |
|---|---|---|---|---|---|---|
| Aqueduct Floods v2 | WRI | Riverine and coastal flood depth, return periods 2–1,000 years; baseline, 2030, 2050 and 2080 under RCP4.5/8.5; no flood protection | Global, about 1 km | CC BY 4.0 | Yes | [Earth Engine catalogue](https://developers.google.com/earth-engine/datasets/catalog/WRI_Aqueduct_Flood_Hazard_Maps_V2); [wri.org](https://www.wri.org/aqueduct) † |
| JRC Global River Flood Hazard Maps v2.1.2 | EC JRC / CEMS-GloFAS | River flood depth, 7 return periods (10–500 years) | Global land, about 90 m | **Conflicting:** the README says ODbL 1.0, `copyright.txt` says CC BY 4.0. **Correction** | Yes under either, but ODbL is share-alike | [README](https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-GLOFAS/flood_hazard/README.txt); [copyright.txt](https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/CEMS-GLOFAS/copyright.txt) |
| Copernicus EMS Rapid Mapping | EU CEMS | Footprints of past events: flood, fire, storm and others | Global, per event | CEMS terms (Reg. (EU) 2021/696): free reproduction, distribution and adaptation with attribution; some products restricted. **Correction** | Yes (commercial use isn't named; with attribution) | [terms](https://mapping.emergency.copernicus.eu/terms-and-conditions/) |
| JRC Global Surface Water | EC JRC / Google | Water occurrence and change, 1984–2024 | Global, 30 m | "Free of charge, without restriction of use" | Yes (cite) | [download page](https://global-surface-water.appspot.com/download) |
| Google Flood Forecasting API | Google | River flood forecasts; discharge reanalysis 1980–2023 | 100+ countries | CC BY 4.0, no charge; API behind a waitlist and key | Yes | [developers.google.com](https://developers.google.com/flood-forecasting) † |
| Global Flood Database v1 | Cloud to Street / DFO | 913 observed flood extents, 2000–2018 | Global, 250 m | CC BY-NC 4.0 | **No** | [Earth Engine catalogue](https://developers.google.com/earth-engine/datasets/catalog/GLOBAL_FLOOD_DB_MODIS_EVENTS_V1) † |
| Fathom Global Flood Map 3 | Fathom (Swiss Re) | Fluvial, pluvial and coastal flood by return period, with climate scenarios | Global, about 30 m | Proprietary. Free non-commercial use in 16 countries through the World Bank; academic licence | **No** (paid) | [fathom.global](https://www.fathom.global/newsroom/world-bank-collaboration/) † |

## Earthquake, landslide, volcano and tsunami
| Source | Publisher | What it gives | Coverage | Licence | Commercial | Checked at |
|---|---|---|---|---|---|---|
| USGS ComCat and ShakeMap | USGS | Earthquake catalogue; shaking footprints | Global | US public domain (except marked third-party images) | Yes | [usgs.gov](https://www.usgs.gov/information-policies-and-instructions/copyrights-and-credits) |
| NASA Global Landslide Catalog / COOLR | NASA GSFC | Rainfall-triggered landslide events, 2007 on, plus citizen reports | Global points | No dataset licence; NASA's default is CC0 unless marked | Yes (cite) | [gpm.nasa.gov](https://gpm.nasa.gov/landslides/data.html) †; [NASA data-use guidance](https://www.earthdata.nasa.gov/engage/open-data-services-software-policies/data-use-guidance) |
| LHASA 2.0 | NASA GSFC | Daily landslide nowcast (hazard probability) | Global, 1 km | US government work; code open source | Yes | [data.gov](https://catalog.data.gov/dataset/global-landslide-nowcast-from-lhasa-l4-1-day-1-km-x-1-km-version-2-0-0-global_landslide_no) †; [GitHub](https://github.com/nasa/lhasa) |
| NCEI Global Historical Tsunami Database | NOAA NCEI | Tsunami events, 2000 BC to present, with run-ups | Global | No licence; US federal; cite doi:10.7289/V5PN93H7 | Yes | [ncei.noaa.gov](https://www.ncei.noaa.gov/products/natural-hazards/tsunamis-earthquakes-volcanoes/tsunamis) |
| GEM Global Seismic Hazard Map v2026.1 | GEM Foundation | Peak ground acceleration on rock, 10% in 50 years | Global | Varies by format: vector data and viewer CC BY-NC-SA 4.0; poster and PNG CC BY-SA 4.0. **Correction** | **No** for the data (a commercial licence is sold); the image only | [globalquakemodel.org](https://www.globalquakemodel.org/product/global-seismic-hazard-map) |
| Volcanoes of the World v5.3.0 | Smithsonian GVP | Holocene volcanoes and eruptions | Global | Smithsonian terms: personal, educational and non-commercial; commercial use needs written permission | **No** (without permission) | [terms of use](https://volcano.si.edu/gvp_termsofuse.cfm) † |

**Gap:** there is no commercially clean global seismic *hazard* map (the probability of a given shaking level). Without one, an answer can give historical seismicity from ComCat, but not a return-period shaking level. [H2](../hazard-tools/spec.md) records this as an open question.

## Heat, drought, wildfire, water and climate projections
| Source | Publisher | What it gives | Coverage | Licence | Commercial | Checked at |
|---|---|---|---|---|---|---|
| ERA5 | ECMWF / C3S | Hourly reanalysis, 1940 to present | Global, 0.25° | CC BY 4.0 | Yes | [CDS](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-single-levels) |
| NEX-GDDP-CMIP6 | NASA NCCS | Daily downscaled CMIP6, historical and 4 SSPs | Global, 0.25° | CC0 on AWS (since September 2022); per model CC BY 4.0 or CC0 on Earth Engine | Yes | [nccs.nasa.gov](https://www.nccs.nasa.gov/services/data-collections/land-based-products/nex-gddp-cmip6) |
| World Bank CCKP CMIP6 | World Bank | Downscaled CMIP6 1950–2100; country and admin statistics | Global, 0.25° | **Conflicting:** CC BY 4.0 in the World Bank catalogue, ODbL in the AWS registry | Yes under either | [World Bank catalogue](https://datacatalog.worldbank.org/search/dataset/0042297); [AWS registry](https://registry.opendata.aws/wbg-cckp) † |
| IPCC AR6 sea-level projections | Garner, Kopp et al. / NASA | Sea-level rise by SSP to 2150, at tide gauges and on a 1° grid | Global | CC BY 4.0 | Yes | [Zenodo](https://zenodo.org/records/5914710); [NASA](https://sealevel.nasa.gov/data/tools/ipcc-ar6-projections-licensing-and-acknowledgements) † |
| CHIRPS v2 (v3 succeeds it) | UCSB Climate Hazards Center | Rainfall, 1981 to present; v2 production ends December 2026 | 50°S–50°N, 0.05° | Copyright waived (public domain) | Yes | [chc.ucsb.edu](https://www.chc.ucsb.edu/data/chirps) |
| GPM IMERG V07 | NASA | Half-hourly precipitation, June 2000 on | Global, 0.1° | NASA data policy (CC0 by default) | Yes | [gpm.nasa.gov FAQ](https://gpm.nasa.gov/data/faq) † |
| NASA FIRMS | NASA | Active fires (MODIS, VIIRS), under 3 hours, with archive | Global | No licence on the page; NASA's default is CC0 | Yes (cite) | [firms.modaps.eosdis.nasa.gov](https://firms.modaps.eosdis.nasa.gov/) |
| SPEIbase v2.11 | CSIC | Drought index (SPEI), 1–48-month scales, 1901–2024 | Global, 0.5° | ODbL 1.0 (contents DbCL) | Yes, share-alike | [spei.csic.es](https://spei.csic.es/database.html) |
| Aqueduct 4.0 Water Risk | WRI | Baseline water stress (1979–2019) and projections to 2030, 2050 and 2080 | Global, sub-basin | CC BY 4.0 | Yes | [wri.org](https://www.wri.org/aqueduct) |
| GWIS | EC JRC / GEO | Burned area and fire events, with country and admin-1 statistics | Global | Not found | Unclear | [gwis.jrc.ec.europa.eu](https://gwis.jrc.ec.europa.eu/) † |
| Global Drought Observatory | EC JRC / CEMS | Drought indicators (CDI, SPI, soil moisture) | Global | No GDO licence found; CEMS material is generally CC BY 4.0 | Unclear (probably yes) | [edo.jrc.ec.europa.eu](https://edo.jrc.ec.europa.eu/world) † |
| Climate Central CoastalDEM v2.1 | Climate Central | Coastal elevation for sea-level and flood analysis | Global coasts | Proprietary; a free non-commercial research version | **No** (paid) | [disclaimer](https://sealevel.climatecentral.org/about/disclaimer) |

## Exposure: people, buildings, land and elevation
| Source | Publisher | What it gives | Coverage | Licence | Commercial | Checked at |
|---|---|---|---|---|---|---|
| GHSL (R2023A/R2024A) | EC JRC | Built-up area, population and urban classes, 1975–2030 | Global, 10 m–1 km | "Reuse authorised with proper acknowledgment" (CC BY 4.0) | Yes | [download page](https://human-settlement.emergency.copernicus.eu/download.php) |
| WorldPop | University of Southampton | Population counts by age and sex, 2015–2030 | Global, 100 m and 1 km | CC BY 4.0; products built on OSM or Microsoft data are ODbL | Yes | [worldpop.org](https://www.worldpop.org/methods/populations/) |
| Meta High Resolution Settlement Layer | Meta / CIESIN | Population density and demographics | Most countries, about 30 m | CC BY 4.0 | Yes | [AWS registry](https://registry.opendata.aws/dataforgood-fb-hrsl/) † |
| Google Open Buildings v3 | Google | 1.8 billion building outlines with confidence | Africa, South and Southeast Asia, Latin America | CC BY 4.0 or ODbL 1.0, at the user's choice | Yes | [sites.research.google](https://sites.research.google/gr/open-buildings/) |
| Microsoft Global ML Building Footprints | Microsoft | About 1.4 billion footprints, some with heights | 225 regions | CDLA Permissive 2.0 | Yes | [GitHub](https://github.com/microsoft/GlobalMLBuildingFootprints) |
| Overture Maps | Overture Maps Foundation | Buildings, places, transport, divisions, addresses | Global | Per theme: ODbL (buildings, transport, base, divisions); CDLA-Permissive 2.0 (places) | Yes (ODbL themes share-alike) | [attribution](https://docs.overturemaps.org/attribution/) |
| ESA WorldCover | ESA | Land cover, 2020 and 2021 | Global, 10 m | CC BY 4.0 | Yes | [esa-worldcover.org](https://esa-worldcover.org/en/data-access) |
| Copernicus DEM GLO-30/90 | ESA / Airbus / DLR | Surface elevation | Global, 30 m and 90 m | Copernicus DEM licence, a "free license" with attribution (the PDF text couldn't be read) | Yes (confirm the text) | [CDSE](https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM) |
| MERIT DEM / MERIT Hydro | University of Tokyo | Error-reduced elevation; hydrography | Global, about 90 m | CC BY-NC 4.0 or ODbL 1.0, at the user's choice | With conditions (ODbL only) | [MERIT DEM](https://global-hydrodynamics.github.io/MERIT_DEM/) |
| HydroSHEDS v1 | WWF / McGill | Hydrologic elevation, flow direction, basins, rivers | Global | HydroSHEDS licence: "free for scientific, educational and commercial use" with attribution | Yes | [hydrosheds.org](https://www.hydrosheds.org/products/hydrosheds) |
| Meta Relative Wealth Index | Meta | Relative wealth estimates (vulnerability) | Low- and middle-income countries, about 2.4 km | Not seen (the page returned 403) | Unclear | [HDX](https://data.humdata.org/dataset/relative-wealth-index) |

## Infrastructure, man-made hazards and conflict
| Source | Publisher | What it gives | Coverage | Licence | Commercial | Checked at |
|---|---|---|---|---|---|---|
| Global Power Plant Database v1.3.0 | WRI | About 35,000 plants: fuel, capacity, generation 2013–17 | Global | CC BY 4.0. **Unmaintained since 2022.** **Correction** | Yes | [GitHub](https://github.com/wri/global-power-plant-database) |
| Global Energy Monitor trackers | Global Energy Monitor | Power, coal, gas and oil assets by unit, status and owner | Global | "CC BY 4.0 unless otherwise noted", with a separate "commercial exemption" request page | Unclear (confirm the exemption) | [download page](https://globalenergymonitor.org/projects/global-integrated-power-tracker/download-data/) † |
| Global Dam Watch v1 | GDW consortium | 41,145 barriers and 35,295 reservoirs | Global | "Free CC BY licence", version not stated. **Correction** (it supersedes GRanD) | Yes | [globaldamwatch.org](https://www.globaldamwatch.org/database) |
| GRanD v1.3 | GWSP / McGill | 7,320 large dams; superseded by GDW | Global | Older v1 metadata says "freely available for non-commercial use" | Unclear; **no** for v1 | [GDW GRanD page](https://www.globaldamwatch.org/grand) |
| OpenStreetMap | OSMF | Roads, buildings, power, industry, pipelines, points of interest | Global | ODbL 1.0 | Yes, share-alike | [osmfoundation.org](https://osmfoundation.org/wiki/Licence) |
| OpenInfraMap | OpenInfraMap | Power, telecom, oil and gas, drawn from OSM | Global | ODbL (the OSM data); CC BY (its analysis) | Yes, share-alike | [about](https://openinframap.org/about) |
| Gridfinder v1.1.1 | Arderne et al. | Predicted medium-voltage grid lines | Global, about 1 km | CC BY 4.0 | Yes | [Zenodo](https://zenodo.org/records/3628142) |
| GDELT | GDELT Project | News-event data, 1979 to present, daily; noisy | Global | "Unlimited and unrestricted use for any academic, commercial, or governmental use", with citation | Yes | [about](https://www.gdeltproject.org/about.html) |
| UCDP GED 26.1 | Uppsala University | Located organised-violence events, 1989–2025 | Global | CC BY 4.0 | Yes | [ucdp.uu.se](https://ucdp.uu.se/downloads/) |
| ACLED | ACLED | Political violence and protest events | Global | ACLED EULA: companies need a corporate licence; governments and multilaterals, ADB included, need a public-sector licence; AI/ML use needs consent. **Correction** | **No** (paid) | [EULA](https://acleddata.com/eula/) |

## Multi-hazard indices and loss records
| Source | Publisher | What it gives | Coverage | Licence | Commercial | Checked at |
|---|---|---|---|---|---|---|
| GIRI | CDRI / UNEP-GRID | Infrastructure average annual loss by hazard and sector, current and under climate scenarios | Global, country and grid | Data: CC BY 3.0 IGO "including for commercial purposes"; the GIR 2025 report itself is CC BY-NC 4.0. **Correction** | Yes (data only) | [download form](https://giri.unepgrid.ch/form/subscribe-for-download-data) |
| INFORM Risk and INFORM Subnational | EC JRC DRMKC | A composite hazard, vulnerability and coping index; subnational for Myanmar, Bangladesh and Central Asia | Global national, some admin-2/3 | No licence on the page (the EC reuse policy probably makes it CC BY 4.0) | Unclear | [drmkc.jrc.ec.europa.eu](https://drmkc.jrc.ec.europa.eu/inform-index/INFORM-Risk/Results-and-data) |
| ThinkHazard! | GFDRR | Hazard level per admin-2 area, 11 hazards | Global | By component: code GPL-3, text CC BY-SA, hazard levels CC BY, source layers under their own terms | With conditions (per layer) | [about](https://thinkhazard.org/en/about) |
| NASA SEDAC multihazard hotspots | CIESIN / World Bank | Multi-hazard frequency, mortality and loss index, about 2000 | Global, 2.5′ | Not confirmed: data.gov "no license", the ODI certificate CC0, mirrors CC BY 4.0. **Correction** | Unclear (probably yes) | [data.gov](https://catalog.data.gov/dataset/global-multihazard-frequency-and-distribution) |
| DesInventar Sendai | UNDRR | Disaster loss records by municipality, 89+ countries | National databases | Software Apache-2.0; **no data licence found**. **Correction** | Unclear | [desinventar.net](https://www.desinventar.net/what_is.html) |
| PCRAFI / PacRIS | SPC / World Bank | Pacific asset exposure; cyclone and earthquake hazard and loss | 14 Pacific island countries and Timor-Leste | "SPREP Public Licence [Open Data]" (terms not found); per-dataset limits in PacRIS. Already a blocked candidate in [R1](../adb-answer-keys/spec.md) | Unclear | [Pacific Data Hub](https://pacificdata.org/data/dataset/pacific-catastrophe-risk-assessment-and-financing-initiative-pf0ce9587-267e-4d0a-a262-88bf6d1fd474) † |
| HDX | UN OCHA | Hazard, exposure and boundary layers from many publishers | Global | Per dataset (CC BY IGO, CC BY, ODbL, ODC-BY, "Other") | Per dataset | [licences](https://docs.humdata.org/about/data-licenses) † |
| EM-DAT | CRED / UCLouvain | Disaster events and losses, 1900 on | Global, by country | EM-DAT terms: "cannot be used for any commercial purpose" without a paid licence; registration | **No** (paid) | [terms of use](https://doc.emdat.be/docs/legal/terms-of-use/) |

## Regional sources for developing Asia-Pacific
| Source | Publisher | What it gives | Coverage | Licence | Commercial | Checked at |
|---|---|---|---|---|---|---|
| ICIMOD Regional Database System | ICIMOD | Glacial lakes, glacial-lake outburst floods, land cover, hazards | Hindu Kush Himalaya | CC BY 4.0 per record (check each one) | Yes, per record | [rds.icimod.org](https://rds.icimod.org/metadata/8881454b-6f7c-461b-95c2-eaf7618230d9) † |
| RIMES (RDAS, DataEx, CDAAS) | RIMES | Climate and hydromet data, downscaled products | South Asia (RDAS: Bangladesh, Nepal, Pakistan) | RDAS described as "open access"; DataEx limited to member weather services; no licence found | Unclear | [rimes.int](https://www.rimes.int/?p=1417) † |
| AHA Centre ADINet | ASEAN AHA Centre | ASEAN disaster events since 2012 | The 10 ASEAN members | "Open to the public"; no licence found | Unclear | [adinet.ahacentre.org](https://adinet.ahacentre.org) † |

**Also important for this region,** from the tables above:
- **Google Open Buildings:** building-level exposure where OSM is thin.
- **WorldPop:** population projected to 2030.
- **IPCC AR6 sea level:** for Pacific atolls and Asian deltas.
- **NEX-GDDP-CMIP6 and CCKP:** heat and rain projections, with admin statistics ready made.
- **Copernicus DEM and JRC Global Surface Water:** commercially clean elevation and flood history.
- **UCDP GED:** conflict events ADB can use without ACLED's public-sector licence (for example Myanmar, Afghanistan, Mindanao).
- **Gridfinder and the solar and wind atlases:** grid distance and resource quality for siting power.

No ADB-published disaster-risk dataset with an open licence was found (data.adb.org's terms page returned 403). ADB may hold layers it can share with us: an open question in [H1](spec.md).

## US only
| Source | Publisher | What it gives | Coverage | Licence | Commercial | Checked at |
|---|---|---|---|---|---|---|
| FEMA National Risk Index v1.20 (December 2025) | FEMA | Expected annual loss, social vulnerability and resilience for 18 hazards, with a rating per hazard | US county and census tract | US federal (the OpenFEMA terms page returned 403). **Correction:** the NRI app is retired; data comes through OpenFEMA and RAPT | Yes | [OpenFEMA changelog](https://www.fema.gov/about/openfema/changelog) † |
| FEMA NFHL | FEMA | Regulatory flood zones (1% and 0.2% annual chance) | US | Not seen (page returned 403); presumed US federal | Probably yes | [fema.gov](https://www.fema.gov/flood-maps/national-flood-hazard-layer) |
| NOAA Storm Events Database | NOAA NCEI | Storm events with damage and deaths, January 1950 on | US county and zone | US federal | Yes | [ncei.noaa.gov](https://www.ncei.noaa.gov/stormevents/ftp.jsp) † |
| First Street | First Street | Property-level climate risk | US | Proprietary | **No** (paid) | [docs.firststreet.org](https://docs.firststreet.org/api) † |

## Engines that tie the data together
| Tool | Publisher | What it does | Licence | Commercial | Checked at |
|---|---|---|---|---|---|
| CLIMADA | ETH Zürich | Probabilistic impact and expected annual loss for an area; cyclone hazard built on IBTrACS and synthetic tracks; adaptation cost-benefit | GPL-3.0 | Yes (copyleft on the software) | [GitHub](https://github.com/CLIMADA-project/climada_python) |
| OpenQuake Engine | GEM Foundation | Seismic hazard and risk calculations | AGPL-3.0, network use included; GEM's models and maps are licensed separately | Yes (copyleft) | [GitHub](https://github.com/gem/oq-engine) |

**Proprietary vendors** (Swiss Re, Munich Re, Moody's RMS, Verisk) weren't re-checked. They are paid products, so they are out of scope.

## Corrections to the original list
- **STORM** (tracks and wind return periods, present and future): CC0, not CC BY 4.0. That is more permissive.
- **JRC river flood maps:** the README says ODbL 1.0 and `copyright.txt` says CC BY 4.0. Both allow commercial use, but ODbL adds share-alike. H1 asks JRC which applies.
- **GIRI:** the data is CC BY 3.0 IGO, so commercial use is allowed. The GIR 2025 report is CC BY-NC 4.0, so don't reuse its figures.
- **GHSL:** "reuse authorised with proper acknowledgment", equivalent to CC BY 4.0, as believed.
- **IBTrACS:** there is no explicit public-domain statement. It is "full and open access" with a WMO Resolution 40 note. It is usable; cite the DOI.
- **Copernicus EMS:** free reuse with attribution, but commercial use isn't named, and some products are restricted.
- **NASA SEDAC multihazard:** its licence is unconfirmed (three sources disagree).
- **DesInventar:** only the software has a licence. No data licence was found.
- **Global Power Plant Database:** CC BY 4.0, but unmaintained since 2022. The Global Energy Monitor trackers are current, once their commercial terms are confirmed.
- **GRanD:** its older metadata says non-commercial. Global Dam Watch supersedes it, and GDW is CC BY.
- **FEMA National Risk Index:** the app is retired. The v1.20 data comes from OpenFEMA and RAPT.
- **GEM seismic hazard map:** the exclusion holds for the data. The poster and PNG are CC BY-SA 4.0, usable as an image only. The current version is v2026.1.
- **Global Flood Database:** CC BY-NC 4.0 confirmed. The exclusion holds.
- **EM-DAT:** non-commercial and registration-only confirmed. A paid licence exists.
- **ACLED:** stricter than thought. Multilaterals such as ADB need a paid public-sector licence, and AI/ML use needs consent.
- **ThinkHazard!:** mixed licences confirmed, set per component.
- **NASA landslide catalog and LHASA:** no dataset licence. They fall under NASA's default (CC0, US government work).

## Couldn't be checked on 2026-11-05
- **No response:** FEMA NFHL and the OpenFEMA terms (403); the SEDAC site and PacRIS (connection refused); the Meta Relative Wealth Index on HDX (403); data.adb.org's terms (403).
- **No licence found:** GWIS, the Global Drought Observatory, INFORM, the UNDRR risk-atlas data (only GAR13 was "CC"), and Google Open Buildings 2.5D Temporal.
- **Text not readable:** the Global Solar Atlas's binding addition and the Copernicus DEM licence PDF.
