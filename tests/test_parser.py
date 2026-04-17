"""Tests for scraper/parser.py HTML parsing logic."""
import pytest
from scraper.parser import _match_map, _parse_card, FUEL_MAP, TRANS_MAP, BODY_MAP, COLOR_MAP
from bs4 import BeautifulSoup


def _make_card(html_inner: str, data_id: str = "123") -> "BeautifulSoup":
    html = f'<article data-id="{data_id}">{html_inner}</article>'
    soup = BeautifulSoup(html, "lxml")
    return soup.find("article")


class TestMatchMap:
    def test_fuel_petrol(self):
        assert _match_map("Benzyna manual", FUEL_MAP) == "Petrol"

    def test_fuel_diesel(self):
        assert _match_map("Some Diesel text", FUEL_MAP) == "Diesel"

    def test_fuel_electric(self):
        assert _match_map("Elektryczny napęd", FUEL_MAP) == "Electric"

    def test_fuel_hybrid(self):
        assert _match_map("Hybryda plugin", FUEL_MAP) == "Hybrid"

    def test_fuel_none(self):
        assert _match_map("totally unrelated text", FUEL_MAP) is None

    def test_trans_manual(self):
        assert _match_map("Manualna skrzynia", TRANS_MAP) == "Manual"

    def test_trans_auto(self):
        assert _match_map("Automatyczna 8-biegowa", TRANS_MAP) == "Automatic"

    def test_color_black(self):
        assert _match_map("Kolor: Czarny metalik", COLOR_MAP) == "Black"

    def test_body_suv(self):
        assert _match_map("Nadwozie: SUV terenowy", BODY_MAP) == "SUV"


class TestParseCard:
    def test_missing_data_id_returns_none(self):
        html = "<article><h2>BMW 3</h2></article>"
        soup = BeautifulSoup(html, "lxml")
        card = soup.find("article")
        result = _parse_card(card)
        assert result is None

    def test_basic_card_returns_dict(self):
        card = _make_card("<h2>Toyota Corolla</h2>")
        result = _parse_card(card)
        assert result is not None
        assert result["url"].endswith("123")
        assert result["brand"] == "Toyota"
        assert result["model"] == "Corolla"

    def test_year_extraction(self):
        card = _make_card("<h2>BMW X5</h2><li>Rok produkcji 2020</li>")
        result = _parse_card(card)
        assert result["year"] == 2020

    def test_mileage_km(self):
        card = _make_card("<h2>Audi A4</h2><dd>85 000 km</dd>")
        result = _parse_card(card)
        assert result["mileage_km"] == 85000

    def test_mileage_tys(self):
        card = _make_card("<h2>Ford Focus</h2><dd>120 tys. km</dd>")
        result = _parse_card(card)
        assert result["mileage_km"] == 120000

    def test_power_km_conversion(self):
        # 136 KM ≈ 100 kW
        card = _make_card("<h2>VW Golf</h2><span>136 KM</span>")
        result = _parse_card(card)
        assert result["power_kw"] == 100

    def test_price_pln_conversion(self):
        card = _make_card("<h2>Skoda Octavia</h2><span>42500 PLN</span>")
        result = _parse_card(card)
        # 42500 / 4.25 = 10000
        assert result["price_eur"] == 10000.0

    def test_price_eur_kept(self):
        card = _make_card("<h2>Mercedes C</h2><span>15000 EUR</span>")
        result = _parse_card(card)
        assert result["price_eur"] == 15000.0

    def test_all_none_graceful(self):
        # card with no useful data — should still return dict, not crash
        card = _make_card("<h2>Unknown</h2>")
        result = _parse_card(card)
        assert isinstance(result, dict)
        assert result["year"] is None
        assert result["mileage_km"] is None

    def test_doors_extraction(self):
        card = _make_card("<h2>VW Passat</h2><li>4 drzwi</li>")
        result = _parse_card(card)
        assert result["doors"] == 4

    def test_fuel_extracted(self):
        card = _make_card("<h2>BMW 320d</h2><li>Diesel manualna</li>")
        result = _parse_card(card)
        assert result["fuel_type"] == "Diesel"
        assert result["transmission"] == "Manual"
