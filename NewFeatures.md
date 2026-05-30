# Shared Running List of New Features to Add
  *** DELETE ONCE ADDED TO PROJECT

ROVER-LIKE FEATURES
    1. AOI Analysis 
        Upload the collected Kismet scans for analysis. 
        Draw multiple areas of interest on a map and query whether similiar selectors were seen across AOIs

    2. KISMETBRIDGE - multi-sensor Kismet dashboard 
        A web-based dashboard for monitoring multiple remote Kismet sensors from one place.
        Each sensor is a Raspberry Pi 4 running Kismet (capturing wireless data) and a WireGuard peer config. 
        The Pi connects over that encrypted tunnel to a VPS, which shares the matching WireGuard config — so the Pi is reachable through the tunnel even when it's behind NAT on a remote network.
        The tool runs as a web UI (on or behind the VPS, inside the tunnel). Through it, a user can:

        Add and manage multiple Pi sensors as "collections"
        Select any sensor and view its live Kismet scan in the browser
        Monitor several field sensors from a single interface instead of logging into each Pi's Kismet page individually
        ALL of this is mapped on the KMZ/KML

 
        
