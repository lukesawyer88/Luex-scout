# Luex Scout

Takes screenshots of websites (competitors, design galleries, dashboards, hero sections) so Claude can review how they look.

- Add URLs to `sites.txt` and push. GitHub Actions opens each page in a real browser and saves screenshots into `shots/<date-time>/`.
- `report.txt` in each batch lists which pages worked and which failed.
