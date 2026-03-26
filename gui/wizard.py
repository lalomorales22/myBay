"""
First-Run Setup Wizard for myBay

A step-by-step wizard that guides the user through:
1. Checking OpenAI API setup
2. Connecting eBay account
3. Setting up business policies
4. Configuring preferences
5. Testing the workflow
"""

import webbrowser
import customtkinter as ctk
from typing import Optional, Callable

from core.presets import MybayPresets, get_presets, save_presets


class SetupWizard(ctk.CTkToplevel):
    """
    First-run setup wizard window.
    
    Guides the user through initial configuration in a friendly,
    step-by-step interface.
    """
    
    def __init__(self, parent=None, on_complete: Callable = None):
        super().__init__(parent)
        
        self.on_complete = on_complete
        self.presets = get_presets()
        self.current_step = 0
        
        # Window setup
        self.title("Welcome to myBay!")
        self.geometry("600x500")
        self.resizable(False, False)
        
        # Center on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 600) // 2
        y = (self.winfo_screenheight() - 500) // 2
        self.geometry(f"+{x}+{y}")
        
        # Make modal
        self.transient(parent)
        self.grab_set()
        
        # Setup UI
        self._setup_ui()
        self._show_step(0)
    
    def _setup_ui(self):
        """Create the wizard UI."""
        # Main container
        self.main_frame = ctk.CTkFrame(self)
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Header
        self.header_label = ctk.CTkLabel(
            self.main_frame,
            text="",
            font=ctk.CTkFont(size=24, weight="bold"),
        )
        self.header_label.pack(pady=(0, 10))
        
        # Progress indicator
        self.progress_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.progress_frame.pack(fill="x", pady=(0, 20))
        
        self.step_labels = []
        steps = ["AI Setup", "eBay", "Location", "Policies", "Done!"]
        for i, step in enumerate(steps):
            label = ctk.CTkLabel(
                self.progress_frame,
                text=f"● {step}",
                font=ctk.CTkFont(size=12),
                text_color="gray50",
            )
            label.pack(side="left", expand=True)
            self.step_labels.append(label)
        
        # Content area
        self.content_frame = ctk.CTkFrame(self.main_frame)
        self.content_frame.pack(fill="both", expand=True, pady=10)
        
        # Button frame
        self.button_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.button_frame.pack(fill="x", pady=(20, 0))
        
        self.back_btn = ctk.CTkButton(
            self.button_frame,
            text="← Back",
            width=100,
            command=self._prev_step,
        )
        self.back_btn.pack(side="left")
        
        self.next_btn = ctk.CTkButton(
            self.button_frame,
            text="Next →",
            width=100,
            command=self._next_step,
        )
        self.next_btn.pack(side="right")
    
    def _show_step(self, step: int):
        """Display a specific step."""
        self.current_step = step
        
        # Update progress indicators
        for i, label in enumerate(self.step_labels):
            if i < step:
                label.configure(text_color="green")
            elif i == step:
                label.configure(text_color="#1f538d")
            else:
                label.configure(text_color="gray50")
        
        # Clear content
        for widget in self.content_frame.winfo_children():
            widget.destroy()
        
        # Show appropriate step
        if step == 0:
            self._show_openai_step()
        elif step == 1:
            self._show_ebay_step()
        elif step == 2:
            self._show_location_step()
        elif step == 3:
            self._show_policies_step()
        elif step == 4:
            self._show_complete_step()
        
        # Update buttons
        self.back_btn.configure(state="normal" if step > 0 else "disabled")
        self.next_btn.configure(text="Finish" if step == 4 else "Next →")
    
    def _show_openai_step(self):
        """Step 1: AI Setup — choose between OpenAI and Ollama."""
        self.header_label.configure(text="🤖 Step 1: AI Setup")

        info = ctk.CTkLabel(
            self.content_frame,
            text="Choose how myBay analyzes your product photos.",
            font=ctk.CTkFont(size=14),
            justify="center",
        )
        info.pack(pady=(10, 15))

        # Backend selector
        self._ai_backend_var = ctk.StringVar(value=self.presets.ai_backend or "auto")

        selector_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        selector_frame.pack(fill="x", padx=30, pady=(0, 10))

        ctk.CTkRadioButton(
            selector_frame,
            text="OpenAI (cloud, paid, best quality + web search)",
            variable=self._ai_backend_var,
            value="openai",
            command=self._on_ai_backend_change,
        ).pack(anchor="w", pady=4)

        ctk.CTkRadioButton(
            selector_frame,
            text="Ollama (local, free, private, no account needed)",
            variable=self._ai_backend_var,
            value="ollama",
            command=self._on_ai_backend_change,
        ).pack(anchor="w", pady=4)

        ctk.CTkRadioButton(
            selector_frame,
            text="Auto-detect (try whatever is available)",
            variable=self._ai_backend_var,
            value="auto",
            command=self._on_ai_backend_change,
        ).pack(anchor="w", pady=4)

        # Status / detail area (swapped based on selection)
        self._ai_detail_frame = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self._ai_detail_frame.pack(fill="both", expand=True, padx=30)

        self._ai_status_label = ctk.CTkLabel(
            self._ai_detail_frame,
            text="",
            font=ctk.CTkFont(size=13),
            justify="center",
        )
        self._ai_status_label.pack(pady=10)

        # Action buttons container
        self._ai_action_frame = ctk.CTkFrame(self._ai_detail_frame, fg_color="transparent")
        self._ai_action_frame.pack()

        self._on_ai_backend_change()

    def _on_ai_backend_change(self):
        """React to AI backend radio button change."""
        choice = self._ai_backend_var.get()
        # Clear action buttons
        for w in self._ai_action_frame.winfo_children():
            w.destroy()

        if choice == "openai":
            self._check_openai()
        elif choice == "ollama":
            self._check_ollama()
        else:
            self._check_auto()

    def _check_openai(self):
        """Check if OpenAI API key is configured and reachable."""
        try:
            from core.vision import ProductAnalyzer
            analyzer = ProductAnalyzer()
            if not analyzer.api_key:
                self._ai_status_label.configure(
                    text="OPENAI_API_KEY not found.\nAdd it to your .env file.",
                    text_color="red",
                )
                ctk.CTkButton(
                    self._ai_action_frame,
                    text="Open OpenAI API Keys",
                    command=lambda: webbrowser.open("https://platform.openai.com/api-keys"),
                ).pack(pady=5)
                ctk.CTkButton(
                    self._ai_action_frame, text="Check Again",
                    width=100, fg_color="gray40",
                    command=self._on_ai_backend_change,
                ).pack(pady=5)
                return

            if analyzer.check_openai_status():
                self._ai_status_label.configure(
                    text=f"OpenAI connected!  Model: {analyzer.model}",
                    text_color="green",
                )
            else:
                self._ai_status_label.configure(
                    text="OpenAI key found but API check failed.\n"
                         "Verify billing, network, and model access.",
                    text_color="orange",
                )
                ctk.CTkButton(
                    self._ai_action_frame, text="Check Again",
                    width=100, fg_color="gray40",
                    command=self._on_ai_backend_change,
                ).pack(pady=5)
        except Exception as e:
            self._ai_status_label.configure(
                text=f"OpenAI check failed: {e}", text_color="red",
            )

    def _check_ollama(self):
        """Check if Ollama is running and has a vision model."""
        try:
            from core.ollama import check_ollama_status, get_ollama_models, has_vision_model

            if not check_ollama_status():
                self._ai_status_label.configure(
                    text="Ollama is not running.\n"
                         "Install it, then start the server:",
                    text_color="orange",
                )
                ctk.CTkLabel(
                    self._ai_action_frame,
                    text="brew install ollama && ollama serve",
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).pack(pady=5)
                ctk.CTkButton(
                    self._ai_action_frame, text="Check Again",
                    width=100, fg_color="gray40",
                    command=self._on_ai_backend_change,
                ).pack(pady=5)
                return

            if not has_vision_model():
                models = get_ollama_models()
                self._ai_status_label.configure(
                    text="Ollama is running but no vision model found.\nPull one:",
                    text_color="orange",
                )
                ctk.CTkLabel(
                    self._ai_action_frame,
                    text="ollama pull llava:7b",
                    font=ctk.CTkFont(size=12, weight="bold"),
                ).pack(pady=5)
                if models:
                    ctk.CTkLabel(
                        self._ai_action_frame,
                        text=f"Available: {', '.join(models[:5])}",
                        font=ctk.CTkFont(size=11), text_color="gray50",
                    ).pack()
                ctk.CTkButton(
                    self._ai_action_frame, text="Check Again",
                    width=100, fg_color="gray40",
                    command=self._on_ai_backend_change,
                ).pack(pady=5)
                return

            models = get_ollama_models()
            self._ai_status_label.configure(
                text=f"Ollama ready!  Models: {', '.join(models[:4])}",
                text_color="green",
            )
        except Exception as e:
            self._ai_status_label.configure(
                text=f"Ollama check failed: {e}", text_color="red",
            )

    def _check_auto(self):
        """Auto-detect which backend is available."""
        try:
            from core.analyzer_factory import detect_available_backend
            backend = detect_available_backend()
            if backend == "openai":
                self._ai_status_label.configure(
                    text="Auto-detected: OpenAI (API key found)",
                    text_color="green",
                )
            elif backend == "ollama":
                self._ai_status_label.configure(
                    text="Auto-detected: Ollama (running locally)",
                    text_color="green",
                )
            else:
                self._ai_status_label.configure(
                    text="No AI backend detected.\n"
                         "Set up OpenAI or Ollama above, then come back.",
                    text_color="orange",
                )
        except Exception as e:
            self._ai_status_label.configure(
                text=f"Detection failed: {e}", text_color="red",
            )

    def _save_ai_backend(self):
        """Save the AI backend choice to presets."""
        choice = getattr(self, "_ai_backend_var", None)
        if choice:
            self.presets.ai_backend = choice.get()
    
    def _show_ebay_step(self):
        """Step 2: Connect eBay account."""
        self.header_label.configure(text="🔗 Step 2: Connect eBay")
        
        info = ctk.CTkLabel(
            self.content_frame,
            text="Connect your eBay seller account to enable listing.\n"
                 "This opens eBay's secure login page.",
            font=ctk.CTkFont(size=14),
            justify="center",
        )
        info.pack(pady=20)
        
        # Status
        self.ebay_status = ctk.CTkLabel(
            self.content_frame,
            text="Not connected",
            font=ctk.CTkFont(size=16),
            text_color="gray50",
        )
        self.ebay_status.pack(pady=10)
        
        # Connect button
        connect_btn = ctk.CTkButton(
            self.content_frame,
            text="Connect eBay Account",
            command=self._connect_ebay,
        )
        connect_btn.pack(pady=10)
        
        # Skip note
        skip_note = ctk.CTkLabel(
            self.content_frame,
            text="You can skip this and connect later in Settings.",
            font=ctk.CTkFont(size=12),
            text_color="gray50",
        )
        skip_note.pack(pady=20)
        
        self._check_ebay_status()
    
    def _check_ebay_status(self):
        """Check eBay connection status."""
        try:
            from ebay.auth import get_auth
            auth = get_auth()
            if auth.config.has_valid_token:
                self.ebay_status.configure(
                    text="✅ eBay account connected!",
                    text_color="green",
                )
            else:
                self.ebay_status.configure(
                    text="Not connected",
                    text_color="gray50",
                )
        except Exception:
            self.ebay_status.configure(
                text="Not connected",
                text_color="gray50",
            )
    
    def _connect_ebay(self):
        """Start eBay OAuth flow."""
        try:
            from ebay.auth import start_auth_flow
            start_auth_flow()
            self.ebay_status.configure(
                text="Check your browser to complete login...",
                text_color="orange",
            )
        except Exception as e:
            self.ebay_status.configure(
                text=f"Error: {e}",
                text_color="red",
            )
    
    def _show_location_step(self):
        """Step 3: Set item location."""
        self.header_label.configure(text="📍 Step 3: Your Location")
        
        info = ctk.CTkLabel(
            self.content_frame,
            text="Where are your items shipped from?",
            font=ctk.CTkFont(size=14),
        )
        info.pack(pady=10)
        
        # Form frame
        form = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        form.pack(pady=20, padx=40, fill="x")
        
        # City
        ctk.CTkLabel(form, text="City:").pack(anchor="w")
        self.city_entry = ctk.CTkEntry(form, width=300)
        self.city_entry.insert(0, self.presets.location.city)
        self.city_entry.pack(pady=(0, 10))
        
        # State
        ctk.CTkLabel(form, text="State:").pack(anchor="w")
        self.state_entry = ctk.CTkEntry(form, width=300)
        self.state_entry.insert(0, self.presets.location.state)
        self.state_entry.pack(pady=(0, 10))
        
        # ZIP
        ctk.CTkLabel(form, text="ZIP Code:").pack(anchor="w")
        self.zip_entry = ctk.CTkEntry(form, width=300)
        self.zip_entry.insert(0, self.presets.location.postal_code)
        self.zip_entry.pack(pady=(0, 10))
    
    def _save_location(self):
        """Save location from form."""
        self.presets.location.city = self.city_entry.get()
        self.presets.location.state = self.state_entry.get()
        self.presets.location.postal_code = self.zip_entry.get()
    
    def _show_policies_step(self):
        """Step 4: Business policies."""
        self.header_label.configure(text="⚙️ Step 4: Listing Defaults")
        
        info = ctk.CTkLabel(
            self.content_frame,
            text="Set your default listing preferences.\n"
                 "These can be changed for individual listings.",
            font=ctk.CTkFont(size=14),
            justify="center",
        )
        info.pack(pady=10)
        
        # Form
        form = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        form.pack(pady=20, padx=40, fill="x")
        
        # Handling time
        ctk.CTkLabel(form, text="Handling Time:").pack(anchor="w")
        self.handling_var = ctk.StringVar(value=str(self.presets.shipping.handling_time))
        handling_menu = ctk.CTkOptionMenu(
            form,
            values=["Same day", "1 business day", "2 business days", "3 business days"],
            width=300,
        )
        handling_menu.set(f"{self.presets.shipping.handling_time} business day(s)")
        handling_menu.pack(pady=(0, 15))
        self.handling_menu = handling_menu
        
        # Returns
        ctk.CTkLabel(form, text="Return Policy:").pack(anchor="w")
        self.returns_var = ctk.StringVar(value="30")
        returns_menu = ctk.CTkOptionMenu(
            form,
            values=["No returns", "14 day returns", "30 day returns", "60 day returns"],
            width=300,
        )
        returns_menu.set(f"{self.presets.returns.return_period} day returns" if self.presets.returns.returns_accepted else "No returns")
        returns_menu.pack(pady=(0, 15))
        self.returns_menu = returns_menu
        
        # Markup
        ctk.CTkLabel(form, text=f"Price Markup: {self.presets.pricing.markup_percent:.0f}%").pack(anchor="w")
        self.markup_slider = ctk.CTkSlider(
            form,
            from_=0,
            to=50,
            number_of_steps=50,
            width=300,
        )
        self.markup_slider.set(self.presets.pricing.markup_percent)
        self.markup_slider.pack(pady=(0, 15))
        
        # Turbo Mode
        self.turbo_var = ctk.BooleanVar(value=self.presets.turbo_mode)
        turbo_check = ctk.CTkCheckBox(
            form,
            text="⚡ Enable Turbo Mode (auto-publish 90%+ confidence)",
            variable=self.turbo_var,
        )
        turbo_check.pack(pady=10)
    
    def _save_policies(self):
        """Save policies from form."""
        # Parse handling time
        handling_text = self.handling_menu.get()
        if "Same day" in handling_text:
            self.presets.shipping.handling_time = 0
        else:
            self.presets.shipping.handling_time = int(handling_text[0])
        
        # Parse returns
        returns_text = self.returns_menu.get()
        if "No returns" in returns_text:
            self.presets.returns.returns_accepted = False
        else:
            self.presets.returns.returns_accepted = True
            self.presets.returns.return_period = int(returns_text.split()[0])
        
        # Markup
        self.presets.pricing.markup_percent = self.markup_slider.get()
        
        # Turbo Mode
        self.presets.turbo_mode = self.turbo_var.get()
    
    def _show_complete_step(self):
        """Step 5: Setup complete!"""
        self.header_label.configure(text="🎉 All Set!")
        
        # Big checkmark
        check = ctk.CTkLabel(
            self.content_frame,
            text="✅",
            font=ctk.CTkFont(size=64),
        )
        check.pack(pady=20)
        
        info = ctk.CTkLabel(
            self.content_frame,
            text="myBay is ready to use!\n\n"
                 "📱 Scan the QR code to snap photos from your phone\n"
                 "🤖 AI will automatically analyze and price items\n"
                 "🚀 One click to publish to eBay",
            font=ctk.CTkFont(size=14),
            justify="center",
        )
        info.pack(pady=20)
        
        tip = ctk.CTkLabel(
            self.content_frame,
            text="Tip: You can change any settings later from\n"
                 "the Settings tab in the main window.",
            font=ctk.CTkFont(size=12),
            text_color="gray50",
            justify="center",
        )
        tip.pack(pady=10)
    
    def _next_step(self):
        """Go to next step."""
        # Save current step data
        if self.current_step == 0:
            self._save_ai_backend()
        elif self.current_step == 2:
            self._save_location()
        elif self.current_step == 3:
            self._save_policies()
        
        if self.current_step < 4:
            self._show_step(self.current_step + 1)
        else:
            self._finish()
    
    def _prev_step(self):
        """Go to previous step."""
        if self.current_step > 0:
            self._show_step(self.current_step - 1)
    
    def _finish(self):
        """Complete the wizard."""
        self.presets.setup_completed = True
        save_presets(self.presets)
        
        if self.on_complete:
            self.on_complete()
        
        self.destroy()


def run_setup_wizard(parent=None, on_complete: Callable = None):
    """
    Show the setup wizard if needed.
    
    Args:
        parent: Parent window (optional)
        on_complete: Callback when setup finishes
    """
    from core.presets import needs_setup
    
    if needs_setup():
        wizard = SetupWizard(parent, on_complete)
        return wizard
    return None


# CLI interface - test the wizard standalone
if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")
    
    # Create a hidden root window
    root = ctk.CTk()
    root.withdraw()
    
    def on_done():
        print("Setup complete!")
        root.quit()
    
    wizard = SetupWizard(on_complete=on_done)
    root.mainloop()
