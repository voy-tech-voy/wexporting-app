"""
Helper utilities for querying the purchases.jsonl audit log.
Provides functions to analyze purchase history, search records, and export data.
"""

import json
import os
from datetime import datetime
from pathlib import Path


class PurchaseAuditLog:
    """Utilities for querying and analyzing purchase audit trail"""
    
    def __init__(self, purchases_file='server/data/purchases.jsonl'):
        self.purchases_file = purchases_file
    
    def get_all_purchases(self):
        """Load all purchase records"""
        purchases = []
        if not os.path.exists(self.purchases_file):
            return purchases
        
        try:
            with open(self.purchases_file, 'r') as f:
                for line in f:
                    if line.strip():
                        purchases.append(json.loads(line))
        except Exception as e:
            print(f"Error reading purchases: {e}")
        
        return purchases
    
    def get_purchases_by_license_key(self, license_key):
        """Get all purchase records for a specific license"""
        purchases = self.get_all_purchases()
        return [p for p in purchases if p.get('license_key') == license_key]
    
    def get_purchases_by_source(self, source):
        """Get all purchases from a specific payment platform"""
        purchases = self.get_all_purchases()
        return [p for p in purchases if p.get('source') == source]
    
    def get_purchases_by_customer(self, customer_id):
        """Get all purchases by a specific customer"""
        purchases = self.get_all_purchases()
        return [p for p in purchases if p.get('customer_id') == customer_id]
    
    def get_purchases_by_email(self, email):
        """Search purchases by customer email (from purchase records)"""
        # Note: Email is not stored directly in purchases.jsonl
        # Use license_key to find emails in licenses.json instead
        purchases = self.get_all_purchases()
        # Can extend this if email is added to purchase_info
        return [p for p in purchases if email.lower() in str(p).lower()]
    
    def get_purchases_by_product(self, product_name):
        """Get purchases of a specific product"""
        purchases = self.get_all_purchases()
        return [p for p in purchases 
                if p.get('product_name', '').lower() == product_name.lower()]
    
    def get_refunded_purchases(self):
        """Get all refunded transactions"""
        purchases = self.get_all_purchases()
        return [p for p in purchases if p.get('is_refunded', False)]
    
    def get_disputed_purchases(self):
        """Get all disputed transactions"""
        purchases = self.get_all_purchases()
        return [p for p in purchases if p.get('is_disputed', False)]
    
    def get_recurring_purchases(self):
        """Get all recurring/subscription purchases"""
        purchases = self.get_all_purchases()
        return [p for p in purchases if p.get('is_recurring', False)]
    
    def get_high_value_purchases(self, min_price=100):
        """Get purchases above a certain price threshold"""
        purchases = self.get_all_purchases()
        result = []
        for p in purchases:
            try:
                price = float(p.get('price', 0))
                if price >= min_price:
                    result.append(p)
            except (ValueError, TypeError):
                pass
        return result
    
    def get_purchases_in_date_range(self, start_date, end_date):
        """Get purchases between two dates"""
        purchases = self.get_all_purchases()
        result = []
        
        try:
            start = datetime.fromisoformat(start_date)
            end = datetime.fromisoformat(end_date)
            
            for p in purchases:
                purchase_date_str = p.get('purchase_date')
                if purchase_date_str:
                    purchase_date = datetime.fromisoformat(purchase_date_str)
                    if start <= purchase_date <= end:
                        result.append(p)
        except Exception as e:
            print(f"Date range error: {e}")
        
        return result
    
    def get_purchase_stats(self):
        """Get statistics about all purchases"""
        purchases = self.get_all_purchases()
        
        if not purchases:
            return {
                'total_purchases': 0,
                'total_revenue': 0,
                'sources': {},
                'top_products': [],
                'average_price': 0
            }
        
        stats = {
            'total_purchases': len(purchases),
            'sources': {},
            'products': {},
            'tiers': {},
            'currencies': {},
            'total_revenue': 0,
            'refunded_count': 0,
            'disputed_count': 0,
            'recurring_count': 0,
            'test_count': 0
        }
        
        for p in purchases:
            # Count by source
            source = p.get('source', 'unknown')
            stats['sources'][source] = stats['sources'].get(source, 0) + 1
            
            # Count by product
            product = p.get('product_name', 'unknown')
            stats['products'][product] = stats['products'].get(product, 0) + 1
            
            # Count by tier
            tier = p.get('tier', 'unknown')
            stats['tiers'][tier] = stats['tiers'].get(tier, 0) + 1
            
            # Count by currency
            currency = p.get('currency', 'unknown')
            stats['currencies'][currency] = stats['currencies'].get(currency, 0) + 1
            
            # Revenue calculation
            try:
                if not p.get('is_refunded', False):
                    price = float(p.get('price', 0))
                    stats['total_revenue'] += price
            except (ValueError, TypeError):
                pass
            
            # Status counts
            if p.get('is_refunded', False):
                stats['refunded_count'] += 1
            if p.get('is_disputed', False):
                stats['disputed_count'] += 1
            if p.get('is_recurring', False):
                stats['recurring_count'] += 1
            if p.get('is_test', False):
                stats['test_count'] += 1
        
        # Sort products by count
        stats['top_products'] = sorted(
            stats['products'].items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # Calculate average
        if purchases:
            non_refunded = [p for p in purchases if not p.get('is_refunded', False)]
            if non_refunded:
                total = sum(float(p.get('price', 0)) for p in non_refunded)
                stats['average_price'] = total / len(non_refunded)
        
        return stats
    
    def export_to_csv(self, filename='purchases_export.csv', filters=None):
        """Export purchases to CSV (optional filters)"""
        purchases = self.get_all_purchases()
        
        # Apply filters if provided
        if filters:
            if 'source' in filters:
                purchases = [p for p in purchases if p.get('source') == filters['source']]
            if 'min_price' in filters:
                purchases = [p for p in purchases 
                           if float(p.get('price', 0)) >= filters['min_price']]
            if 'product' in filters:
                purchases = [p for p in purchases 
                           if p.get('product_name') == filters['product']]
        
        if not purchases:
            print("No purchases to export")
            return False
        
        try:
            import csv
            
            # Get all possible fields
            all_fields = set()
            for p in purchases:
                all_fields.update(p.keys())
            
            fieldnames = sorted(list(all_fields))
            
            with open(filename, 'w', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(purchases)
            
            print(f"Exported {len(purchases)} records to {filename}")
            return True
        except Exception as e:
            print(f"Export error: {e}")
            return False


# Example usage
if __name__ == '__main__':
    audit = PurchaseAuditLog()
    
    print("=" * 70)
    print("PURCHASE AUDIT LOG ANALYSIS")
    print("=" * 70)
    
    # Get stats
    stats = audit.get_purchase_stats()
    print(f"\n📊 Purchase Statistics:")
    print(f"  Total Purchases: {stats['total_purchases']}")
    print(f"  Total Revenue: ${stats['total_revenue']:.2f}")
    print(f"  Average Price: ${stats['average_price']:.2f}")
    print(f"  Refunded: {stats['refunded_count']}")
    print(f"  Disputed: {stats['disputed_count']}")
    print(f"  Recurring: {stats['recurring_count']}")
    print(f"  Test: {stats['test_count']}")
    
    print(f"\n📦 By Source:")
    for source, count in stats['sources'].items():
        print(f"  {source}: {count}")
    
    print(f"\n💰 Top Products:")
    for product, count in stats['top_products'][:5]:
        print(f"  {product}: {count} sales")
    
    print(f"\n🎯 By Tier:")
    for tier, count in sorted(stats['tiers'].items(), key=lambda x: x[1], reverse=True):
        print(f"  {tier}: {count}")
    
    # Show refunded purchases
    refunded = audit.get_refunded_purchases()
    if refunded:
        print(f"\n⚠️  Refunded Purchases ({len(refunded)}):")
        for p in refunded:
            print(f"  - {p.get('license_key')}: {p.get('product_name')} (${p.get('price')})")
    
    # Show recent Gumroad purchases
    gumroad = audit.get_purchases_by_source('gumroad')
    if gumroad:
        print(f"\n🔗 Recent Gumroad Purchases ({len(gumroad)} total):")
        for p in gumroad[-5:]:  # Last 5
            print(f"  - {p.get('license_key')}: {p.get('customer_id')} (${p.get('price')} {p.get('currency')})")
    
    print("\n" + "=" * 70)
