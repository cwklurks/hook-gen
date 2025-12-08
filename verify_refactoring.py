#!/usr/bin/env python3
"""
Verification script for the refactoring.
Run this to ensure everything works after the shared library migration.
"""

import sys
from pathlib import Path


def test_hookgen_core_imports():
    """Test that hookgen_core can be imported and has all expected exports."""
    print("🔍 Testing hookgen_core imports...")
    
    try:
        import hookgen_core
        print(f"  ✅ hookgen_core imported successfully (v{hookgen_core.__version__})")
    except ImportError as e:
        print(f"  ❌ Failed to import hookgen_core: {e}")
        print("  💡 Run: pip install -e packages/hookgen_core")
        return False
    
    # Test critical exports
    required_exports = [
        # rhythm
        'load_mono', 'estimate_bpm_and_beats', 'ticks_from_beats', 'groove_histogram',
        # motif
        'list_available_scales', 'sample_rhythm', 'midi_mapper', 'assign_pitches',
        'generate_motif', 'vary_motif', 'generate_structured_hook', 'detect_scale_from_audio',
        # export
        'notes_to_midi_bytes', 'notes_to_wav_bytes', 'hooks_to_wav_bytes',
        # ui_helpers
        'build_zip_name',
    ]
    
    missing = []
    for name in required_exports:
        if not hasattr(hookgen_core, name):
            missing.append(name)
    
    if missing:
        print(f"  ❌ Missing exports: {', '.join(missing)}")
        return False
    
    print(f"  ✅ All {len(required_exports)} required exports present")
    return True


def test_backend_imports():
    """Test that backend can import from hookgen_core."""
    print("\n🔍 Testing backend imports...")
    
    # Add backend to path
    backend_path = Path(__file__).parent / "backend"
    if backend_path not in sys.path:
        sys.path.insert(0, str(backend_path))
    
    try:
        # Test main.py imports
        from hookgen_core import detect_scale_from_audio, estimate_bpm_and_beats
        print("  ✅ Backend imports from hookgen_core work")
        
        # Test that old imports are gone
        try:
            from app import rhythm
            if hasattr(rhythm, 'estimate_bpm_and_beats'):
                print("  ⚠️  WARNING: Old app.rhythm still exists (should be deleted)")
                return False
        except ImportError:
            print("  ✅ Old app.rhythm correctly removed")
        
        return True
    except ImportError as e:
        print(f"  ❌ Backend import failed: {e}")
        return False


def test_hookaid_imports():
    """Test that hook-aid can import from hookgen_core."""
    print("\n🔍 Testing hook-aid imports...")
    
    try:
        from hookgen_core import (
            assign_pitches,
            estimate_bpm_and_beats,
            list_available_scales,
            notes_to_wav_bytes,
        )
        print("  ✅ Hook-aid imports from hookgen_core work")
        
        # Check that old files are gone
        hookaid_path = Path(__file__).parent / "hook-aid"
        old_files = ['rhythm.py', 'motif.py', 'export.py', 'ui_helpers.py', 'pkg_resources.py']
        found_old = [f for f in old_files if (hookaid_path / f).exists()]
        
        if found_old:
            print(f"  ⚠️  WARNING: Old files still exist: {', '.join(found_old)}")
            return False
        
        print("  ✅ Old duplicate files correctly removed")
        return True
    except ImportError as e:
        print(f"  ❌ Hook-aid import failed: {e}")
        return False


def test_fast_mode_parameters():
    """Test that fast_mode parameters work correctly."""
    print("\n🔍 Testing fast_mode parameters...")
    
    try:
        import numpy as np
        from hookgen_core import detect_scale_from_audio, estimate_bpm_and_beats
        
        # Create dummy audio
        dummy_audio = np.random.uniform(-0.1, 0.1, 22050).astype(np.float32)
        sr = 22050
        
        # Test rhythm fast_mode
        tempo1, beats1 = estimate_bpm_and_beats(dummy_audio, sr, fast_mode=False)
        tempo2, beats2 = estimate_bpm_and_beats(dummy_audio, sr, fast_mode=True)
        print("  ✅ estimate_bpm_and_beats fast_mode parameter works")
        print(f"     - Accurate mode: {tempo1:.1f} BPM")
        print(f"     - Fast mode: {tempo2:.1f} BPM")
        
        # Test scale detection fast_mode
        scale1, score1 = detect_scale_from_audio(dummy_audio, sr, fast_mode=False)
        scale2, score2 = detect_scale_from_audio(dummy_audio, sr, fast_mode=True)
        print("  ✅ detect_scale_from_audio fast_mode parameter works")
        print(f"     - Accurate mode: {scale1} ({score1:.3f})")
        print(f"     - Fast mode: {scale2} ({score2:.3f})")
        
        return True
    except Exception as e:
        print(f"  ❌ Fast mode test failed: {e}")
        return False


def test_both_apis():
    """Test that both hook-aid and backend APIs work."""
    print("\n🔍 Testing both API styles...")
    
    try:
        import numpy as np
        from hookgen_core import (
            assign_pitches,
            generate_structured_hook,  # backend style
            sample_rhythm,  # hook-aid style
        )
        
        histogram = np.ones(16) / 16.0
        
        # Hook-aid style
        events = sample_rhythm(histogram, density=7, seed=42)
        notes_simple = assign_pitches(events, scale="C minor", seed=42)
        print(f"  ✅ Hook-aid API (assign_pitches): {len(notes_simple)} notes")
        
        # Backend style
        notes_structured = generate_structured_hook(
            histogram, scale="C minor", density=7, seed=42
        )
        print(f"  ✅ Backend API (generate_structured_hook): {len(notes_structured)} notes (4-bar)")
        
        return True
    except Exception as e:
        print(f"  ❌ API test failed: {e}")
        return False


def check_file_structure():
    """Verify the correct file structure."""
    print("\n🔍 Checking file structure...")
    
    root = Path(__file__).parent
    
    # Check shared package exists
    required_files = [
        "packages/hookgen_core/__init__.py",
        "packages/hookgen_core/pyproject.toml",
        "packages/hookgen_core/rhythm.py",
        "packages/hookgen_core/motif.py",
        "packages/hookgen_core/export.py",
    ]
    
    for file_path in required_files:
        full_path = root / file_path
        if not full_path.exists():
            print(f"  ❌ Missing: {file_path}")
            return False
    
    print(f"  ✅ All {len(required_files)} core files present")
    
    # Check old files are removed
    old_files = [
        "backend/app/rhythm.py",
        "backend/app/motif.py",
        "backend/app/export.py",
        "hook-aid/rhythm.py",
        "hook-aid/motif.py",
        "hook-aid/export.py",
    ]
    
    remaining = [f for f in old_files if (root / f).exists()]
    if remaining:
        print(f"  ⚠️  Old files still exist: {', '.join(remaining)}")
        return False
    
    print("  ✅ All duplicate files removed")
    return True


def main():
    """Run all verification tests."""
    print("=" * 60)
    print("🚀 Hook-Gen Refactoring Verification")
    print("=" * 60)
    
    tests = [
        ("File Structure", check_file_structure),
        ("Core Package Imports", test_hookgen_core_imports),
        ("Backend Integration", test_backend_imports),
        ("Hook-aid Integration", test_hookaid_imports),
        ("Fast Mode Parameters", test_fast_mode_parameters),
        ("Both API Styles", test_both_apis),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"  ❌ Unexpected error: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    print(f"\n{'✅' if passed == total else '❌'} {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Refactoring successful!")
        print("\n📝 Next steps:")
        print("   1. Test docker-compose: docker-compose build backend")
        print("   2. Run backend: cd backend && uvicorn main:app --reload")
        print("   3. Run hook-aid: cd hook-aid && streamlit run app.py")
        return 0
    else:
        print("\n⚠️  Some tests failed. Please review the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

