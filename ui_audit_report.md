# UI Audit & Bug Report: MovieBox Sync

This document summarizes the current technical debt and user-experience issues identified in the MovieBox Sync (Movieknight) desktop application.

## 1. Console Warnings & Technical Errors
### **[BUG] QFont Initialization Warning**
*   **Symptom**: `QFont::setPointSize: Point size <= 0 (-1), must be greater than 0` appears in the terminal at startup.
*   **Root Cause**: Likely triggered by the use of unsupported CSS properties in QSS (e.g., `letter-spacing`, `text-transform`) or uninitialized font point sizes in parent `QWidget` rules.
*   **Expectation**: The console should be clean of warnings during normal application lifecycle.

---

## 2. Layout & Responsiveness Issues
### **[BUG] Element Collapsing (Device Selector & Footer)**
*   **Symptom**: The Device Selector in the setup page and the Library Footer in the results page have "weird heights" that seem to collapse into themselves or overlap adjacent elements.
*   **Root Cause**: Over-reliance on `setFixedHeight()` and `setFixedWidth()` on parent containers without proper internal padding or layout stretches.
*   **Expectation**: UI elements should have consistent, flexible heights with healthy internal padding that adapts to the content and window size.

### **[BUG] Grid Alignment Inconsistency**
*   **Symptom**: When the library contains only a few items (e.g., 1 or 2 videos), they are centered in the middle of the screen rather than starting at the top-left (1,1) position.
*   **Root Cause**: `QGridLayout` alignment is set to `AlignCenter` for cards, and the grid lacks trailing spacers to anchor items to the top-left.
*   **Expectation**: The media grid should always follow a standard reading pattern (Top-Left to Bottom-Right), regardless of item count.

### **[UX] Lack of General Spacing & Padding**
*   **Symptom**: The UI feels crowded; elements are too close to each other, lacking professional standard "breathing room."
*   **Root Cause**: Missing layout margins and standard spacing tokens in core layouts.
*   **Expectation**: A "Zen" design with luxurious, consistent spacing between sections and a premium feel.

---

## 3. Interaction & Rendering Quality
### **[BUG] Search Flicker Effect**
*   **Symptom**: While typing in the search bar, a "weird little window flicker" occurs—elements seem to appear and disappear in a rapid, glitchy fashion.
*   **Root Cause**: The grid is being fully cleared and re-rendered on every single keystroke. This causes a split-second "blank" state that creates a strobe effect.
*   **Expectation**: Search results should update smoothly. A short "debounce" timer (e.g., 150ms) should be used to wait for the user to pause typing before triggering a grid re-render.

---

## Summary of Resolution Plan
1.  **Global Font Guard**: Set a valid default font in `app.py`.
2.  **QSS Sanitization**: Strip unsupported properties and standardize spacing.
3.  **Responsive Layouts**: Replace fixed dimensions with `setMaximum`/`setMinimum` and proper layout stretches.
4.  **Debounced Search**: Throttle search updates to eliminate flickers.
5.  **Grid Anchoring**: Fix grid logic to start from (0,0).
