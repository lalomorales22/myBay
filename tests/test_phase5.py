"""
Test Suite for Phase 5: Polish, Packaging & Pro Features

Run with: pytest tests/test_phase5.py -v
"""

import os
import sys
import pytest
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestPricing:
    """Tests for the pricing intelligence module."""
    
    def test_import_pricing(self):
        """Test importing pricing module."""
        from ebay.pricing import (
            PricingIntelligence,
            PricingAnalysis,
            ComparableItem,
            get_pricing,
        )
        assert PricingIntelligence is not None
        assert PricingAnalysis is not None
    
    def test_pricing_analysis_dataclass(self):
        """Test PricingAnalysis data structure."""
        from ebay.pricing import PricingAnalysis, ComparableItem
        
        analysis = PricingAnalysis(
            query="test product",
            comparable_count=5,
            average_price=50.0,
            median_price=45.0,
            min_price=30.0,
            max_price=80.0,
            suggested_price=42.75,
            price_range_low=35.0,
            price_range_high=65.0,
            comparables=[],
        )
        
        assert analysis.query == "test product"
        assert analysis.suggested_price == 42.75
        assert analysis.comparable_count == 5
    
    def test_price_advice_too_low(self):
        """Test price advice for too-low prices."""
        from ebay.pricing import PricingAnalysis
        
        analysis = PricingAnalysis(
            query="test",
            comparable_count=10,
            average_price=50.0,
            median_price=50.0,
            min_price=30.0,
            max_price=70.0,
            suggested_price=50.0,
            price_range_low=40.0,
            price_range_high=60.0,
        )
        
        # 35 is 30% below 50
        assert analysis.is_price_too_low(35.0)
        assert "below market" in analysis.get_price_advice(35.0).lower()
    
    def test_price_advice_competitive(self):
        """Test price advice for competitive prices."""
        from ebay.pricing import PricingAnalysis
        
        analysis = PricingAnalysis(
            query="test",
            comparable_count=10,
            average_price=50.0,
            median_price=50.0,
            min_price=30.0,
            max_price=70.0,
            suggested_price=50.0,
            price_range_low=40.0,
            price_range_high=60.0,
        )
        
        # 48 is within range
        assert not analysis.is_price_too_low(48.0)
        assert not analysis.is_price_too_high(48.0)
        assert "competitive" in analysis.get_price_advice(48.0).lower()


class TestTurboMode:
    """Tests for Turbo Mode auto-publishing."""
    
    def test_import_turbo(self):
        """Test importing turbo module."""
        from core.turbo import TurboMode, get_turbo, is_turbo_enabled
        assert TurboMode is not None
    
    def test_turbo_enable_disable(self, tmp_path):
        """Test enabling and disabling Turbo Mode."""
        # Use temp database
        from data.database import Database
        from core.turbo import TurboMode
        
        db = Database(tmp_path / "test.db")
        turbo = TurboMode()
        turbo.db = db
        
        turbo.enable(threshold=0.85)
        assert turbo.enabled
        assert turbo.confidence_threshold == 0.85
        
        turbo.disable()
        assert not turbo.enabled
    
    def test_should_auto_publish(self, tmp_path):
        """Test auto-publish qualification check."""
        from data.database import Database, Draft
        from core.turbo import TurboMode
        
        db = Database(tmp_path / "test.db")
        turbo = TurboMode()
        turbo.db = db
        turbo.enabled = True
        turbo.confidence_threshold = 0.90
        
        high_confidence_draft = Draft(
            sku="TEST-HIGH",
            title="High Confidence Item",
            description="Test",
            condition="NEW",
            price=50.0,
            image_paths=[],
            ai_confidence=0.95,
        )
        
        low_confidence_draft = Draft(
            sku="TEST-LOW",
            title="Low Confidence Item",
            description="Test",
            condition="NEW",
            price=50.0,
            image_paths=[],
            ai_confidence=0.80,
        )
        
        assert turbo.should_auto_publish(high_confidence_draft)
        assert not turbo.should_auto_publish(low_confidence_draft)


class TestRetry:
    """Tests for error handling and retry logic."""
    
    def test_import_retry(self):
        """Test importing retry module."""
        from core.retry import (
            with_retry,
            APIError,
            APIException,
            ErrorType,
            classify_error,
        )
        assert with_retry is not None
    
    def test_classify_401_error(self):
        """Test classifying auth errors."""
        from core.retry import classify_error, ErrorType
        
        error = classify_error(status_code=401)
        assert error.error_type == ErrorType.AUTH_EXPIRED
        assert error.retryable
    
    def test_classify_429_error(self):
        """Test classifying rate limit errors."""
        from core.retry import classify_error, ErrorType
        
        error = classify_error(status_code=429)
        assert error.error_type == ErrorType.RATE_LIMITED
        assert error.retryable
    
    def test_classify_500_error(self):
        """Test classifying server errors."""
        from core.retry import classify_error, ErrorType
        
        error = classify_error(status_code=500)
        assert error.error_type == ErrorType.SERVER_ERROR
        assert error.retryable
    
    def test_retry_config(self):
        """Test retry configuration."""
        from core.retry import RetryConfig
        
        config = RetryConfig(
            max_retries=5,
            base_delay=2.0,
            max_delay=60.0,
        )
        
        assert config.max_retries == 5
        assert config.get_delay(0) == 2.0
        assert config.get_delay(1) == 4.0
        assert config.get_delay(2) == 8.0
        assert config.get_delay(10) == 60.0  # Capped at max


class TestPresets:
    """Tests for myBay Presets (Smart Defaults)."""
    
    def test_import_presets(self):
        """Test importing presets module."""
        from core.presets import (
            MybayPresets,
            ShippingPreset,
            ReturnPreset,
            LocationPreset,
            PricingPreset,
            get_presets,
        )
        assert MybayPresets is not None
    
    def test_shipping_preset(self):
        """Test shipping preset defaults."""
        from core.presets import ShippingPreset
        
        preset = ShippingPreset()
        assert preset.carrier == "USPS"
        assert preset.handling_time == 1
        
        preset.handling_time = 2
        data = preset.to_dict()
        restored = ShippingPreset.from_dict(data)
        assert restored.handling_time == 2
    
    def test_pricing_preset_apply(self):
        """Test applying pricing rules."""
        from core.presets import PricingPreset
        
        preset = PricingPreset(
            markup_percent=10.0,
            round_to_99=True,
            minimum_price=5.00,
        )
        
        # 50 + 10% = 55, rounded to 55.99
        result = preset.apply_to_price(50.0)
        assert result == 55.99
        
        # Minimum price test
        result = preset.apply_to_price(3.0)
        assert result >= 5.00
    
    def test_presets_serialization(self, tmp_path):
        """Test saving and loading presets."""
        from data.database import Database
        from core.presets import MybayPresets
        
        # Setup temp database
        db = Database(tmp_path / "test.db")
        
        presets = MybayPresets()
        presets.shipping.handling_time = 3
        presets.location.city = "Los Angeles"
        presets.location.state = "CA"
        presets.turbo_mode = True
        
        # Save to database
        import data.database
        original_get_db = data.database.get_db
        data.database.get_db = lambda: db
        
        try:
            presets.save()
            loaded = MybayPresets.load()
            
            assert loaded.shipping.handling_time == 3
            assert loaded.location.city == "Los Angeles"
            assert loaded.turbo_mode == True
        finally:
            data.database.get_db = original_get_db
    
    def test_is_ready_to_list(self):
        """Test readiness check."""
        from core.presets import MybayPresets
        
        presets = MybayPresets()
        assert not presets.is_ready_to_list
        
        presets.payment_policy_id = "policy1"
        presets.return_policy_id = "policy2"
        presets.fulfillment_policy_id = "policy3"
        presets.location.postal_code = "90210"
        
        assert presets.is_ready_to_list


class TestSetupWizard:
    """Tests for the First-Run Setup Wizard."""
    
    def test_import_wizard(self):
        """Test importing wizard module."""
        try:
            from gui.wizard import SetupWizard, run_setup_wizard
            assert SetupWizard is not None
        except ImportError as e:
            if "customtkinter" in str(e).lower():
                pytest.skip("CustomTkinter not installed")
            raise
    
    def test_needs_setup(self, tmp_path):
        """Test needs_setup check."""
        from data.database import Database
        from core.presets import MybayPresets, needs_setup
        
        db = Database(tmp_path / "test.db")
        
        import data.database
        original_get_db = data.database.get_db
        data.database.get_db = lambda: db
        
        try:
            # Fresh database - needs setup
            assert needs_setup()
            
            # Mark setup as complete
            presets = MybayPresets()
            presets.setup_completed = True
            presets.save()
            
            # Reset presets cache
            import core.presets
            core.presets._presets = None
            
            assert not needs_setup()
        finally:
            data.database.get_db = original_get_db
            import core.presets
            core.presets._presets = None


class TestBuildScript:
    """Tests for the build script."""
    
    def test_build_script_exists(self):
        """Test that build.py exists."""
        build_path = Path(__file__).parent.parent / "build.py"
        assert build_path.exists()
    
    def test_spec_file_exists(self):
        """Test that PyInstaller spec file exists."""
        spec_path = Path(__file__).parent.parent / "myBay.spec"
        assert spec_path.exists()


class TestNgrok:
    """Tests for ngrok helper behavior."""

    def test_import_ngrok(self):
        """Test importing ngrok module."""
        from core.ngrok import ensure_ngrok_tunnel, find_ngrok_binary
        assert ensure_ngrok_tunnel is not None
        assert find_ngrok_binary is not None

    def test_find_ngrok_binary_from_env(self, tmp_path, monkeypatch):
        """Test NGROK_PATH override is honored."""
        from core.ngrok import find_ngrok_binary

        fake_ngrok = tmp_path / "ngrok"
        fake_ngrok.write_text("#!/bin/sh\necho ngrok\n")
        fake_ngrok.chmod(0o755)

        monkeypatch.setenv("NGROK_PATH", str(fake_ngrok))
        found = find_ngrok_binary()
        assert found == fake_ngrok

    def test_get_https_tunnel_url_for_port(self, monkeypatch):
        """Test selecting matching HTTPS tunnel for specific local port."""
        from core.ngrok import get_https_tunnel_url
        import core.ngrok as ngrok_mod

        monkeypatch.setattr(
            ngrok_mod,
            "_read_tunnels",
            lambda: [
                {"proto": "https", "public_url": "https://aaa.ngrok-free.app", "config": {"addr": "http://localhost:9000"}},
                {"proto": "https", "public_url": "https://bbb.ngrok-free.app", "config": {"addr": "http://localhost:8000"}},
            ],
        )

        assert get_https_tunnel_url(8000) == "https://bbb.ngrok-free.app"

    def test_ensure_ngrok_tunnel_reuses_existing(self, monkeypatch):
        """Test that existing tunnel is reused without starting a new process."""
        from core.ngrok import ensure_ngrok_tunnel
        import core.ngrok as ngrok_mod

        monkeypatch.setattr(ngrok_mod, "get_https_tunnel_url", lambda port: "https://existing.ngrok-free.app")

        result = ensure_ngrok_tunnel(port=8000)
        assert result.running
        assert result.public_url == "https://existing.ngrok-free.app"
        assert not result.started_by_app


class TestModuleImports:
    """Test that all Phase 5 modules can be imported."""
    
    def test_import_all_core_modules(self):
        """Test importing all core modules."""
        from core import (
            ProductAnalyzer,
            QueueWatcher,
            get_turbo,
            get_presets,
            APIError,
        )
    
    def test_import_all_ebay_modules(self):
        """Test importing all eBay modules."""
        from ebay import (
            get_config,
            get_auth,
            get_taxonomy,
            get_inventory,
            get_pricing,
        )
    
    def test_import_gui_modules(self):
        """Test importing GUI modules."""
        try:
            from gui import MyBayApp, SetupWizard
        except ImportError as e:
            if "customtkinter" in str(e).lower():
                pytest.skip("CustomTkinter not installed")
            raise


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
