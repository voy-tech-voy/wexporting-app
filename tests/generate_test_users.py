"""
Generate Test User Profiles for IAP Testing

Creates 100 mock users with various states:
- Free tier users (daily 50 credits)
- Premium lifetime users
- Users with purchased credits (various amounts)
- Users with active day passes
- Users with expired day passes
- Mixed scenarios
"""

import json
import random
from datetime import datetime, timedelta
from pathlib import Path


def generate_user_id():
    """Generate a random MS Store-style user ID"""
    import uuid
    return str(uuid.uuid4())


def generate_test_users(count=100):
    """Generate test user profiles"""
    users = {}
    now = datetime.utcnow()
    
    # Distribution targets
    targets = {
        'free_tier': 40,           # 40% free users
        'premium_lifetime': 15,    # 15% lifetime premium
        'purchased_credits': 25,   # 25% users with purchased credits
        'active_day_pass': 10,     # 10% active day pass
        'expired_day_pass': 5,     # 5% expired day pass
        'mixed': 5                 # 5% mixed (premium + credits)
    }
    
    user_count = 0
    
    # 1. Free Tier Users (40)
    for i in range(targets['free_tier']):
        user_id = generate_user_id()
        users[user_id] = {
            'store_user_id': user_id,
            'platform': 'msstore',
            'energy_balance': random.randint(0, 50),  # Varying usage
            'purchased_energy': 0,
            'is_premium': False,
            'last_energy_refresh': now.isoformat(),
            'created_at': (now - timedelta(days=random.randint(1, 365))).isoformat(),
            'profile_type': 'free_tier'
        }
        user_count += 1
    
    # 2. Premium Lifetime Users (15)
    for i in range(targets['premium_lifetime']):
        user_id = generate_user_id()
        users[user_id] = {
            'store_user_id': user_id,
            'platform': 'msstore',
            'energy_balance': 999,  # Unlimited
            'purchased_energy': 0,
            'is_premium': True,
            'last_energy_refresh': now.isoformat(),
            'created_at': (now - timedelta(days=random.randint(30, 730))).isoformat(),
            'profile_type': 'premium_lifetime'
        }
        user_count += 1
    
    # 3. Users with Purchased Credits (25)
    for i in range(targets['purchased_credits']):
        user_id = generate_user_id()
        purchased = random.choice([50, 100, 200, 500, 1000])
        free = random.randint(0, 50)
        users[user_id] = {
            'store_user_id': user_id,
            'platform': 'msstore',
            'energy_balance': free + purchased,
            'purchased_energy': purchased,
            'is_premium': False,
            'last_energy_refresh': now.isoformat(),
            'created_at': (now - timedelta(days=random.randint(1, 180))).isoformat(),
            'profile_type': 'purchased_credits'
        }
        user_count += 1
    
    # 4. Active Day Pass Users (10)
    for i in range(targets['active_day_pass']):
        user_id = generate_user_id()
        # Day pass expires in 1-23 hours
        expiry = now + timedelta(hours=random.randint(1, 23))
        users[user_id] = {
            'store_user_id': user_id,
            'platform': 'msstore',
            'energy_balance': random.randint(0, 50),
            'purchased_energy': 0,
            'is_premium': False,
            'premium_expiry': expiry.isoformat(),
            'last_energy_refresh': now.isoformat(),
            'created_at': (now - timedelta(days=random.randint(1, 90))).isoformat(),
            'profile_type': 'active_day_pass'
        }
        user_count += 1
    
    # 5. Expired Day Pass Users (5)
    for i in range(targets['expired_day_pass']):
        user_id = generate_user_id()
        # Day pass expired 1-30 days ago
        expiry = now - timedelta(days=random.randint(1, 30))
        users[user_id] = {
            'store_user_id': user_id,
            'platform': 'msstore',
            'energy_balance': random.randint(0, 50),
            'purchased_energy': 0,
            'is_premium': False,
            'premium_expiry': expiry.isoformat(),
            'last_energy_refresh': now.isoformat(),
            'created_at': (now - timedelta(days=random.randint(30, 180))).isoformat(),
            'profile_type': 'expired_day_pass'
        }
        user_count += 1
    
    # 6. Mixed (Premium + Purchased Credits) (5)
    for i in range(targets['mixed']):
        user_id = generate_user_id()
        purchased = random.choice([100, 500, 1000])
        users[user_id] = {
            'store_user_id': user_id,
            'platform': 'msstore',
            'energy_balance': 999,  # Premium unlimited
            'purchased_energy': purchased,  # Also has purchased credits (edge case)
            'is_premium': True,
            'last_energy_refresh': now.isoformat(),
            'created_at': (now - timedelta(days=random.randint(90, 730))).isoformat(),
            'profile_type': 'mixed_premium_credits'
        }
        user_count += 1
    
    return users


def save_test_users(users, filepath):
    """Save users to JSON file"""
    with open(filepath, 'w') as f:
        json.dump(users, f, indent=2)
    print(f"✓ Saved {len(users)} test users to {filepath}")


def print_summary(users):
    """Print summary of generated users"""
    from collections import Counter
    
    types = Counter(u['profile_type'] for u in users.values())
    
    print("\n" + "=" * 60)
    print("TEST USER GENERATION SUMMARY")
    print("=" * 60)
    print(f"Total Users: {len(users)}")
    print("\nDistribution:")
    for profile_type, count in types.items():
        print(f"  - {profile_type}: {count}")
    
    # Calculate totals
    total_purchased = sum(u.get('purchased_energy', 0) for u in users.values())
    premium_count = sum(1 for u in users.values() if u.get('is_premium'))
    active_day_pass = sum(1 for u in users.values() 
                          if u.get('premium_expiry') and 
                          datetime.fromisoformat(u['premium_expiry']) > datetime.utcnow())
    
    print(f"\nStatistics:")
    print(f"  - Total Purchased Credits: {total_purchased:,}")
    print(f"  - Lifetime Premium Users: {premium_count}")
    print(f"  - Active Day Passes: {active_day_pass}")
    print("=" * 60)


if __name__ == "__main__":
    # Generate users
    users = generate_test_users(100)
    
    # Save to test data file
    output_path = Path(__file__).parent.parent / 'server' / 'data' / 'test_user_profiles.json'
    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_test_users(users, output_path)
    
    # Print summary
    print_summary(users)
    
    print(f"\n✓ Test data ready at: {output_path}")
    print(f"✓ Use this file to test server logic without affecting production data")
