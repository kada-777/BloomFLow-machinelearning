import json

from ml.data import load_training_data, profile_training_data
from ml.supabase_client import create_supabase_client


def main() -> None:
    """Fetch and print a read-only profile of the Supabase training data."""
    client = create_supabase_client()
    tables = load_training_data(client)
    profile = profile_training_data(tables)
    print(json.dumps(profile, indent=2, default=str))


if __name__ == "__main__":
    main()
