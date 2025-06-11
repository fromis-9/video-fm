#!/usr/bin/env python3
"""
Test script for Phase 1 modularization
"""

def test_imports():
    """Test that all modules can be imported."""
    print("🧪 Testing imports...")
    try:
        from core.api.lastfm_client import create_lastfm_client, LastFmClient
        from core.api.youtube_client import create_youtube_client, YouTubeClient
        from core.utils.cache import load_cache, save_cache, clear_cache
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_client_creation():
    """Test that API clients can be created."""
    print("🧪 Testing API client creation...")
    try:
        from core.api.lastfm_client import create_lastfm_client
        from core.api.youtube_client import create_youtube_client
        
        # Test Last.fm client
        lastfm_client = create_lastfm_client("test_key")
        print(f"✅ Last.fm client created: {type(lastfm_client).__name__}")
        
        # Test YouTube client
        youtube_client = create_youtube_client("test_key")
        print(f"✅ YouTube client created: {type(youtube_client).__name__}")
        
        return True
    except Exception as e:
        print(f"❌ Client creation failed: {e}")
        return False

def test_error_handling():
    """Test error handling for invalid inputs."""
    print("🧪 Testing error handling...")
    try:
        from core.api.lastfm_client import create_lastfm_client
        from core.api.youtube_client import create_youtube_client
        
        # Test empty API key
        try:
            create_lastfm_client("")
            print("❌ Should have failed with empty API key")
            return False
        except ValueError:
            print("✅ Empty API key validation works")
        
        try:
            create_youtube_client("")
            print("❌ Should have failed with empty API key")
            return False
        except ValueError:
            print("✅ Empty API key validation works")
            
        return True
    except Exception as e:
        print(f"❌ Error handling test failed: {e}")
        return False

def test_cache_functionality():
    """Test cache utilities."""
    print("🧪 Testing cache functionality...")
    try:
        from core.utils.cache import load_cache, save_cache
        import os
        
        # Test save and load
        test_data = {"test": "data", "number": 42}
        save_cache(test_data, "test_cache.json")
        
        loaded_data = load_cache("test_cache.json")
        if loaded_data == test_data:
            print("✅ Cache save/load works")
        else:
            print(f"❌ Cache data mismatch: {loaded_data} != {test_data}")
            return False
            
        # Clean up
        cache_dir = os.path.join(os.path.dirname(__file__), "cache")
        test_file = os.path.join(cache_dir, "test_cache.json")
        if os.path.exists(test_file):
            os.remove(test_file)
            
        return True
    except Exception as e:
        print(f"❌ Cache test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Running Phase 1 Modularization Tests")
    print("=" * 50)
    
    tests = [
        test_imports,
        test_client_creation,
        test_error_handling,
        test_cache_functionality
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! Phase 1 modularization is working perfectly.")
        return True
    else:
        print("❌ Some tests failed. Please check the output above.")
        return False

if __name__ == "__main__":
    main() 