# Add Image Upload Functionality to DeSo Python SDK

## 📸 Overview
This PR adds native image upload functionality to the DeSo Python SDK, enabling developers to upload images directly to DeSo's media service and include them in posts.

## ✨ Features Added

### `upload_image()` Method
- **Purpose**: Upload image files to DeSo and receive hosted URLs
- **Returns**: Image URL that can be used in `submit_post()` via `image_urls` parameter
- **Error Handling**: Comprehensive error handling for file operations and HTTP requests
- **Integration**: Seamlessly works with existing `submit_post()` method

### Usage Example
```python
# Upload an image
image_url = client.upload_image('chart.png')

# Use in a post
post_response = client.submit_post(
    updater_public_key_base58check=PUBLIC_KEY,
    body="Check out this performance chart!",
    image_urls=[image_url],  # Include uploaded image
    # ... other parameters
)
```

## 🔧 Implementation Details

### Method Signature
```python
def upload_image(
    self,
    image_path: str,
    extra_headers: Optional[Dict[str, str]] = None,
) -> str
```

### Parameters
- `image_path`: Path to the image file to upload
- `extra_headers`: Optional additional HTTP headers

### Returns
- `str`: The hosted image URL from DeSo's media service

### Error Handling
- `FileNotFoundError`: When image file doesn't exist
- `requests.exceptions.HTTPError`: For HTTP-related errors
- `json.JSONDecodeError`: For response parsing errors
- `ValueError`: When ImageURL is missing from response

## 🚀 Use Cases

### 1. **Automated Analytics Bots**
```python
# Generate performance chart
create_performance_chart('daily_performance.png')

# Upload and post
image_url = client.upload_image('daily_performance.png')
client.submit_post(
    body="📊 Daily Performance Summary",
    image_urls=[image_url]
)
```

### 2. **Rich Social Applications**
```python
# User uploads profile picture
image_url = client.upload_image(user_uploaded_file)
client.submit_post(
    body="Updated my profile picture!",
    image_urls=[image_url]
)
```

### 3. **Content Management Systems**
```python
# Batch upload multiple images
image_urls = []
for image_path in image_files:
    url = client.upload_image(image_path)
    image_urls.append(url)

client.submit_post(
    body="Photo gallery from today's event",
    image_urls=image_urls
)
```

## 🔍 Technical Implementation

### API Integration
- Uses DeSo's `/api/v0/upload-image` endpoint
- Supports multipart/form-data uploads
- Handles automatic image resizing by DeSo service
- Follows existing SDK patterns and error handling

### Code Quality
- Comprehensive docstrings following SDK conventions
- Type hints for all parameters and return values
- Consistent error handling patterns
- No breaking changes to existing functionality

## 📚 Documentation Updates

### Enhanced Examples
- Added commented example in `main()` function
- Updated `submit_post` example to show `image_urls` usage
- Clear usage patterns for common scenarios

### Code Comments
- Detailed inline documentation
- Usage examples within the code
- Integration guidance for developers

## ✅ Testing

### Real-World Testing
- **Production Tested**: Successfully deployed in [DesoMonitor](https://github.com/carry2web/DesoMonitor)
- **Live Usage**: Daily automated posts with performance charts
- **Error Scenarios**: Tested with missing files, network errors, various image formats
- **Integration**: Confirmed compatibility with `submit_post` method

### Test Scenarios Covered
- ✅ PNG image uploads
- ✅ Integration with existing `submit_post` method
- ✅ Error handling for missing files
- ✅ Network error scenarios
- ✅ Various image sizes and formats
- ✅ Multiple images per post

## 🎯 Benefits

### For Developers
- **Simple API**: Easy-to-use method following SDK conventions
- **Rich Media Posts**: Enable image content in DeSo applications
- **Automation Ready**: Perfect for bots and automated systems
- **Production Ready**: Battle-tested in real applications

### For DeSo Ecosystem
- **Enhanced Content**: More engaging posts with visual content
- **Developer Adoption**: Easier to build rich social applications
- **Analytics Tools**: Enable data visualization sharing
- **Community Growth**: Support for visual content creators

## 🔗 Related Work
- Complements existing `submit_post()` method
- Uses DeSo's official image upload endpoint
- Follows DeSo media upload documentation
- No dependencies on external image hosting services

## 📝 Breaking Changes
**None** - This is purely additive functionality that doesn't modify existing methods or behavior.

## 🤝 Community Impact
This feature enables the DeSo developer community to build:
- 📊 Analytics and monitoring tools that share visual reports
- 🤖 Bots that post charts, graphs, and data visualizations  
- 📱 Social applications with rich media content
- 🛠️ Content management systems with native image support

---

**Ready for review!** This feature is production-tested and follows all SDK conventions. Happy to address any feedback or questions! 🚀
