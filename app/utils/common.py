from bson import ObjectId

def convert_objectid_to_str(document):
    """Convert MongoDB ObjectId to string and handle nested documents"""
    if document is None:
        return None
    
    if isinstance(document, list):
        return [convert_objectid_to_str(item) for item in document]
    
    if isinstance(document, dict):
        result = {}
        for key, value in document.items():
            if key == '_id' and isinstance(value, ObjectId):
                result[key] = str(value)
                result['id'] = str(value)  # Alias for frontend
            elif key == 'id' and isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, ObjectId):
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = convert_objectid_to_str(value)
            elif isinstance(value, list):
                result[key] = [convert_objectid_to_str(item) for item in value]
            else:
                result[key] = value
        return result
    
    return document
