# Video Worker — Phase 4 Placeholder

This service will be implemented in **Phase 4** (Automatic Clip Processing).

**Planned responsibilities:**
- Receive job queue events when a delivery is marked as a 4 or 6
- Load the matching video recording from InsForge Storage
- Use FFmpeg to extract the clip window (delivery timestamp ± buffer seconds)
- Upload the extracted clip back to InsForge Storage (`cricket-videos` bucket)
- Associate the clip with the correct player in the database

**Technology:** Python 3.11, FFmpeg, background job queue (TBD in Phase 4)
