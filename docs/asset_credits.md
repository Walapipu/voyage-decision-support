# Image, icon and map credits

## OceanFlow logo

The crown logo in `assets/oceanflow-crown.png` was supplied by the user on 30 October 2026. The original PNG and its transparency are preserved.

## Representative photographs

The case's MF/MV vessels are fictional. These are photographs of real bulk carriers used as representative illustrations, not identity claims or photographs of those fictional vessels. The source thumbnails are stored locally, avoiding an image API key or request on every page load. Display thumbnails may be cropped with CSS; original downloaded files are unchanged.

All four photos are used under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Attribution and source metadata are preserved in `assets/photos/sources.json`. The photographs retain their original licence; no endorsement is implied.

- `bulker-1.jpg`: **Key Future**, by **Veggies**, [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Key-Future-Kamsarmax-Bulk-Carrier-in-Baltimore-Harbor.jpg).
- `bulker-2.jpg`: **African Loon**, by **Calistemon**, [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Bulk_carrier_African_Loon_of_the_coast_of_Western_Australia.jpg).
- `bulker-3.jpg`: **Bulk carrier, aerial view**, by **Alet123**, [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Bulk_carrier_ship_view_from_top.jpg).
- `bulker-4.jpg`: **Nava Dionyssos**, by **Niels Johannes**, [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Nava_Dionyssos_(IMO_9608673)_Liverpool_2025.jpg).

## Icons

Sidebar and KPI icons: [Lucide](https://lucide.dev), ISC licence (with upstream Feather MIT notices), copied from [lucide-icons/lucide](https://github.com/lucide-icons/lucide). Full notice: `assets/icons/LICENSE`. Native interactive controls use Streamlit's Material Symbols support.

## Detailed map

- [Leaflet](https://leafletjs.com/) 1.9.4, loaded from the pinned public unpkg CDN.
- [OpenStreetMap](https://www.openstreetmap.org/copyright) raster tiles, with attribution visible on the map. No API key is required. Dark mode applies a display filter. Follow the [tile usage policy](https://operations.osmfoundation.org/policies/tiles/) for deployment; no bulk downloading or offline caching is implemented.
- Country borders and labels: [Natural Earth](https://www.naturalearthdata.com/about/terms-of-use/), public domain. The bundled 1:110m overview GeoJSON comes from [natural-earth-vector](https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_admin_0_countries.geojson), with properties reduced to label fields. Borders are cartographic context, not claims about sovereignty. Detailed zoom tiles remain OpenStreetMap.
- Zoom controls provide more geographic detail. Internet is required; WebGL is not. A tile-loading error is shown if unavailable.
- Display-only port-vicinity coordinates and individual source links are in `data/map_locations.json`. These are not berth positions. Kamsar is explicitly an approximate industrial-area reference. Source codes are the teaching-case aliases, not asserted official UN/LOCODE equivalences.
- Dashed port-to-port links show the relationship between legs, not navigable sea routes. No live positions, congestion, canal routing or weather is claimed. The economics engine continues to use the original frozen CSV distances, not map geometry.

## Local profile

The name menu edits a session-only display name and role. “Log out” clears local Streamlit session state and displays a session-ended screen. It is not account authentication and does not delete the server's configured API key.
