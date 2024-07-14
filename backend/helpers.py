from flask import current_app
import numpy as np

def get_db():
    return current_app.config['db']

def get_features():
    return current_app.config['features']

def get_reverse_category_mapping():
    return current_app.config['reverse_category_mapping']

def get_tfidf():
    return current_app.config['tfidf']

def get_df():
    return current_app.config['df']

def get_coordinate_scaler():
    return current_app.config['coordinate_scaler']



def get_user_profile(user_id, tfidf, coordinate_scaler):
    db = get_db()
    user = db['User']
    features = get_features()
    reverse_category_mapping = get_reverse_category_mapping()
    df = get_df()

    if not list(user.find_one({'_id': user_id})):
        return np.zeros(features.shape[1])
    
    user_vector = np.zeros(features.shape[1])
    user_data = list(user.find({'_id': user_id}))[0]
    # print('user data: ',user_data)
    general_prefs = user_data['general_preferences']
    for category in general_prefs['categories']:
        mapped_category = reverse_category_mapping.get(category, category)
        if mapped_category in tfidf.vocabulary_:
            user_vector[tfidf.vocabulary_[mapped_category]] = 1
    
    price_index = features.shape[1] - 4 + len(general_prefs['price'])
    user_vector[price_index] = 1
    
    user_coords = np.array(general_prefs['coordinates']).reshape(1, -1)
    # Create a dummy array with 4 features to match the scaler's expected input
    dummy_coords = np.zeros((1, 4))
    dummy_coords[0, 2:] = user_coords  # Assuming latitude and longitude are the last two features
    scaled_coords = coordinate_scaler.transform(dummy_coords)
    user_vector[-6:-4] = scaled_coords[0, 2:] 

    for spot_id, spot_data in user_data['location_specific'].items():
        spot_index = df[df['id'] == spot_id].index
        if len(spot_index) > 0:
            spot_index = spot_index[0]
            
            if not spot_data.get('time_viewing', True):
                # User pressed details, incorporate positive interactions
                interaction_weight = 1.0
                
                if spot_data.get('pressed_share', False):
                    interaction_weight += 0.3
                if spot_data.get('pressed_save', False):
                    interaction_weight += 0.3
                
                # Incorporate viewing time
                max_viewing_time = 60
                viewing_time = min(spot_data.get('time_viewing', 0), max_viewing_time)
                time_factor = viewing_time / max_viewing_time
                interaction_weight *= (1 + time_factor)
                
                # Incorporate rating with penalty for low ratings
                rating = spot_data.get('rating', 2.5)
                if rating < 3:
                    # Apply penalty that increases as rating approaches 1
                    penalty = 1 - (rating - 1) / 2  # This will be 1 at rating 1, and 0 at rating 3
                    interaction_weight *= (1 - penalty * 0.5)  # Adjust the 0.5 to control penalty strength
                
                # Add to user vector
                user_vector += features[spot_index] * interaction_weight
            
            else:
                # User didn't press details, subtract a fraction of the feature vector
                user_vector -= features[spot_index] * 0.2
    
    norm = np.linalg.norm(user_vector)
    if norm > 0:
        user_vector /= norm
    
    return user_vector
