import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier 
from sklearn.metrics import accuracy_score, classification_report
from sklearn.preprocessing import LabelEncoder
import joblib

# Step 1: Load the dataset
DATA_FILE = "data/day2_sample.csv"

df = pd.read_csv(DATA_FILE)

print("Dataset loaded successfully!")
print("Dataset shape:", df.shape)
print("\nFirst 5 rows:")
print(df.head())

# Step 2: Handle missing values
df = df.dropna()

# Step 3: Separate features and target
# Sensor readings are the input features
X = df[
    ["temperature", "pressure", "vibration", "current", "rpm"]
]

# State is the target to predict
y = df["state"]

# Step 4: Encode the target labels
label_encoder = LabelEncoder()
y = label_encoder.fit_transform(y)

# Step 5: Split dataset into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(
    X,
    y,
    test_size=0.2,
    random_state=42,
    stratify=y
)

print("\nTraining samples:", len(X_train))
print("Testing samples:", len(X_test))

# Step 6: Create and train the model
model = RandomForestClassifier(
    n_estimators=100,
     random_state=42,
     class_weight="balanced"
)
model = 
model.fit(X_train, y_train)

print("\nModel training completed!")

# Step 7: Predict using test data
y_pred = model.predict(X_test)

# Step 8: Calculate accuracy
accuracy = accuracy_score(y_test, y_pred)

print(f"\nModel Accuracy: {accuracy * 100:.2f}%")

# Step 9: Display classification report
print("\nClassification Report:")
print(
    classification_report(
        y_test,
        y_pred,
        labels=list(range(len(label_encoder.classes_))),
        target_names=label_encoder.classes_,
        zero_division=0
    )
)

# Step 10: Save the trained model
joblib.dump(model, "machine_state_model.pkl")
joblib.dump(label_encoder, "state_label_encoder.pkl")

print("\nModel saved as machine_state_model.pkl")
print("Label encoder saved as state_label_encoder.pkl")
