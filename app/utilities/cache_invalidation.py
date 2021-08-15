import boto3
import time

# Create CloudFront client
from django.conf import settings
from zappa.async import task

cf = boto3.client('cloudfront')

# Enter Original name


def get_distribution_id():
    return "distribution_id"


# Create CloudFront invalidation
@task
def create_invalidation():
    print("cache_invalidation")
    if settings.SITE_CODE == 2 or settings.SITE_CODE == 3:
        res = cf.create_invalidation(
            DistributionId=get_distribution_id(),
            InvalidationBatch={
                'Paths': {
                    'Quantity': 1,
                    'Items': [
                        '/*'
                    ]
                },
                'CallerReference': str(time.time()).replace(".", "")
            }
        )
        invalidation_id = res['Invalidation']['Id']
        return invalidation_id


# # Create CloudFront Invalidation
# id = create_invalidation()
# print("Invalidation created successfully with Id: " + id)