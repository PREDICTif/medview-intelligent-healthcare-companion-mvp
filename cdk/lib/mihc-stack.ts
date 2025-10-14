import * as cdk from 'aws-cdk-lib';
import { Construct } from 'constructs';
import {
  Bucket,
  BucketProps,
  BlockPublicAccess,
  BucketEncryption,
  ObjectOwnership,
} from 'aws-cdk-lib/aws-s3';

export class MihcStack extends cdk.Stack {
  public readonly rawBucket: Bucket;
  public readonly processedBucket: Bucket;
  public readonly curatedBucket: Bucket;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // Common bucket properties for security and best practices
    const bucketCommonProps: BucketProps = {
      blockPublicAccess: BlockPublicAccess.BLOCK_ALL,
      encryption: BucketEncryption.S3_MANAGED,
      // autoDeleteObjects: true,
      // removalPolicy: cdk.RemovalPolicy.DESTROY,
      objectOwnership: ObjectOwnership.OBJECT_WRITER,
      enforceSSL: true,
      versioned: true,
    };

    // Raw data bucket - for incoming unprocessed data
    this.rawBucket = new Bucket(this, 'RawBucket', bucketCommonProps);

    // Processed data bucket - for data that has been processed/transformed
    this.processedBucket = new Bucket(this, 'ProcessedBucket', bucketCommonProps);

    // Curated data bucket - for final, clean, ready-to-use data
    this.curatedBucket = new Bucket(this, 'CuratedBucket', bucketCommonProps);

    // Add lifecycle rules for cost optimization
    this.rawBucket.addLifecycleRule({
      id: 'RawDataLifecycle',
      enabled: true,
      transitions: [
        {
          storageClass: cdk.aws_s3.StorageClass.INFREQUENT_ACCESS,
          transitionAfter: cdk.Duration.days(30),
        },
        {
          storageClass: cdk.aws_s3.StorageClass.GLACIER,
          transitionAfter: cdk.Duration.days(90),
        },
      ],
    });

    this.processedBucket.addLifecycleRule({
      id: 'ProcessedDataLifecycle',
      enabled: true,
      transitions: [
        {
          storageClass: cdk.aws_s3.StorageClass.INFREQUENT_ACCESS,
          transitionAfter: cdk.Duration.days(60),
        },
      ],
    });

    // Output bucket names and ARNs for reference
    new cdk.CfnOutput(this, 'RawBucketName', {
      value: this.rawBucket.bucketName,
      description: 'Name of the raw data S3 bucket',
    });

    new cdk.CfnOutput(this, 'ProcessedBucketName', {
      value: this.processedBucket.bucketName,
      description: 'Name of the processed data S3 bucket',
    });

    new cdk.CfnOutput(this, 'CuratedBucketName', {
      value: this.curatedBucket.bucketName,
      description: 'Name of the curated data S3 bucket',
    });

    new cdk.CfnOutput(this, 'RawBucketArn', {
      value: this.rawBucket.bucketArn,
      description: 'ARN of the raw data S3 bucket',
    });

    new cdk.CfnOutput(this, 'ProcessedBucketArn', {
      value: this.processedBucket.bucketArn,
      description: 'ARN of the processed data S3 bucket',
    });

    new cdk.CfnOutput(this, 'CuratedBucketArn', {
      value: this.curatedBucket.bucketArn,
      description: 'ARN of the curated data S3 bucket',
    });
  }
}