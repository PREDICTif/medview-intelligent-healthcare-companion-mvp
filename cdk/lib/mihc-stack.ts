import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as iam from "aws-cdk-lib/aws-iam";
import * as s3 from "aws-cdk-lib/aws-s3";
import * as rds from "aws-cdk-lib/aws-rds";
import * as ec2 from "aws-cdk-lib/aws-ec2";
import * as kms from "aws-cdk-lib/aws-kms";
import * as logs from "aws-cdk-lib/aws-logs";
// import * as glue from "@aws-cdk/aws-glue-alpha";

// export interface MihcStackProps extends cdk.StackProps {
//   stageName: string;
// }

export class MihcStack extends cdk.Stack {
  public readonly rawBucket: s3.Bucket;
  public readonly processedBucket: s3.Bucket;
  public readonly curatedBucket: s3.Bucket;
  public readonly archiveBucket: s3.Bucket;
  public readonly scriptBucket: s3.Bucket;
  public readonly vpc: ec2.Vpc;
  public readonly auroraCluster: rds.DatabaseCluster;
  public readonly databaseKmsKey: kms.Key;
  public readonly databaseSecurityGroup: ec2.SecurityGroup;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // constructor(scope: Construct, id: string, props: MihcStackProps) {
    //   super(scope, id, props);

    const account = cdk.Stack.of(this).account;

    this.rawBucket = new s3.Bucket(
      this,
      "RawBucket"
      // , {
      // bucketName: `dl-rawbucket-${account}`,
      // }
    );
    this.processedBucket = new s3.Bucket(
      this,
      "ProcessedBucket"
      // , {
      // bucketName: `dl-processedbucket-${account}`,
      // }
    );
    this.curatedBucket = new s3.Bucket(
      this,
      "CuratedBucket"
      // , {
      // bucketName: `dl-curatedbucket-${account}`,
      // }
    );
    this.archiveBucket = new s3.Bucket(
      this,
      "ArchiveBucket"
      // , {
      // bucketName: `dl-archivebucket-${account}`,
      // }
    );
    this.scriptBucket = new s3.Bucket(
      this,
      "ScriptBucket"
      // , {
      // bucketName: `dl-scriptbucket-${account}`,
      // }
    );

    // Create VPC for Aurora with HIPAA compliance
    this.vpc = new ec2.Vpc(this, "MihcVpc", {
      maxAzs: 3, // Multi-AZ for high availability (HIPAA requirement)
      natGateways: 2, // Redundant NAT gateways for availability
      enableDnsHostnames: true,
      enableDnsSupport: true,
      subnetConfiguration: [
        {
          cidrMask: 24,
          name: "public",
          subnetType: ec2.SubnetType.PUBLIC,
        },
        {
          cidrMask: 24,
          name: "private",
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
        },
        {
          cidrMask: 24,
          name: "isolated",
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
        },
      ],
    });

    // Create KMS key for database encryption (HIPAA requirement)
    this.databaseKmsKey = new kms.Key(this, "DatabaseKmsKey", {
      description: "KMS key for HIPAA-compliant medical database encryption",
      enableKeyRotation: true, // Required for HIPAA
      removalPolicy: cdk.RemovalPolicy.RETAIN, // Protect encryption key
      policy: new iam.PolicyDocument({
        statements: [
          new iam.PolicyStatement({
            sid: "Enable IAM User Permissions",
            effect: iam.Effect.ALLOW,
            principals: [new iam.AccountRootPrincipal()],
            actions: ["kms:*"],
            resources: ["*"],
          }),
          new iam.PolicyStatement({
            sid: "Allow RDS Service",
            effect: iam.Effect.ALLOW,
            principals: [new iam.ServicePrincipal("rds.amazonaws.com")],
            actions: [
              "kms:Decrypt",
              "kms:GenerateDataKey",
              "kms:CreateGrant",
              "kms:DescribeKey",
            ],
            resources: ["*"],
          }),
          new iam.PolicyStatement({
            sid: "Allow CloudWatch Logs Service",
            effect: iam.Effect.ALLOW,
            principals: [
              new iam.ServicePrincipal(`logs.${cdk.Stack.of(this).region}.amazonaws.com`)
            ],
            actions: [
              "kms:Encrypt",
              "kms:Decrypt",
              "kms:ReEncrypt*",
              "kms:GenerateDataKey*",
              "kms:CreateGrant",
              "kms:DescribeKey",
            ],
            resources: ["*"],
            conditions: {
              ArnLike: {
                "kms:EncryptionContext:aws:logs:arn": `arn:aws:logs:${cdk.Stack.of(this).region}:${account}:log-group:/aws/rds/cluster/*`,
              },
            },
          }),
        ],
      }),
    });

    // Add alias for the KMS key
    new kms.Alias(this, "DatabaseKmsKeyAlias", {
      aliasName: "alias/mihc-medical-database",
      targetKey: this.databaseKmsKey,
    });

    // Create security group for database with strict access controls
    this.databaseSecurityGroup = new ec2.SecurityGroup(this, "DatabaseSecurityGroup", {
      vpc: this.vpc,
      description: "Security group for HIPAA-compliant medical database",
      allowAllOutbound: false, // Explicit outbound rules only
    });

    // Only allow PostgreSQL traffic from within VPC
    this.databaseSecurityGroup.addIngressRule(
      ec2.Peer.ipv4(this.vpc.vpcCidrBlock),
      ec2.Port.tcp(5432),
      "PostgreSQL access from VPC only"
    );

    // Create CloudWatch log group for database logs with encryption
    const databaseLogGroup = new logs.LogGroup(this, "DatabaseLogGroup", {
      logGroupName: "/aws/rds/cluster/mihc-medical-database/postgresql",
      retention: logs.RetentionDays.ONE_YEAR, // HIPAA requires log retention
      encryptionKey: this.databaseKmsKey,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    // Create HIPAA-compliant Aurora PostgreSQL cluster
    this.auroraCluster = new rds.DatabaseCluster(this, "MedicalDatabase", {
      engine: rds.DatabaseClusterEngine.auroraPostgres({
        version: rds.AuroraPostgresEngineVersion.VER_15_4,
      }),
      credentials: rds.Credentials.fromGeneratedSecret("postgres", {
        secretName: "mihc-medical-database-credentials",
        encryptionKey: this.databaseKmsKey,
      }),
      writer: rds.ClusterInstance.provisioned("writer", {
        instanceType: ec2.InstanceType.of(ec2.InstanceClass.T4G, ec2.InstanceSize.MEDIUM),
        enablePerformanceInsights: true, // For monitoring and compliance
        performanceInsightEncryptionKey: this.databaseKmsKey,
        performanceInsightRetention: rds.PerformanceInsightRetention.MONTHS_12,
      }),
      readers: [
        rds.ClusterInstance.provisioned("reader1", {
          instanceType: ec2.InstanceType.of(ec2.InstanceClass.T4G, ec2.InstanceSize.MEDIUM),
          enablePerformanceInsights: true,
          performanceInsightEncryptionKey: this.databaseKmsKey,
          performanceInsightRetention: rds.PerformanceInsightRetention.MONTHS_12,
        }),
        // rds.ClusterInstance.provisioned("reader2", {
        //   instanceType: ec2.InstanceType.of(ec2.InstanceClass.T4G, ec2.InstanceSize.MEDIUM),
        //   enablePerformanceInsights: true,
        //   performanceInsightEncryptionKey: this.databaseKmsKey,
        //   performanceInsightRetention: rds.PerformanceInsightRetention.MONTHS_12,
        // }),
      ],
      vpc: this.vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_ISOLATED, // No internet access
      },
      securityGroups: [this.databaseSecurityGroup],
      backup: {
        retention: cdk.Duration.days(35), // HIPAA requires 30+ days
        preferredWindow: "03:00-04:00", // Low-traffic window
      },
      preferredMaintenanceWindow: "sun:04:00-sun:05:00",
      cloudwatchLogsExports: ["postgresql"], // All database logs
      storageEncrypted: true,
      storageEncryptionKey: this.databaseKmsKey, // Customer-managed key
      monitoringInterval: cdk.Duration.seconds(60), // Enhanced monitoring
      monitoringRole: new iam.Role(this, "DatabaseMonitoringRole", {
        assumedBy: new iam.ServicePrincipal("monitoring.rds.amazonaws.com"),
        managedPolicies: [
          iam.ManagedPolicy.fromAwsManagedPolicyName("service-role/AmazonRDSEnhancedMonitoringRole"),
        ],
      }),
      deletionProtection: true, // Prevent accidental deletion
      removalPolicy: cdk.RemovalPolicy.RETAIN, // Retain for compliance
      defaultDatabaseName: "medical_records",
      parameterGroup: new rds.ParameterGroup(this, "DatabaseParameterGroup", {
        engine: rds.DatabaseClusterEngine.auroraPostgres({
          version: rds.AuroraPostgresEngineVersion.VER_15_4,
        }),
        description: "HIPAA-compliant parameter group for medical database",
        parameters: {
          // Enable SSL/TLS encryption in transit
          "rds.force_ssl": "1",
          // Enable logging for audit trail
          "log_statement": "all",
          "log_min_duration_statement": "0",
          "log_connections": "1",
          "log_disconnections": "1",
          // "log_checkpoints": "1",
          "log_lock_waits": "1",
          // Set timezone
          "timezone": "UTC",
        },
      }),
    });

    new cdk.CfnOutput(this, "RawBucketName", {
      value: this.rawBucket.bucketName,
    });
    new cdk.CfnOutput(this, "ProcessedBucketName", {
      value: this.processedBucket.bucketName,
    });
    new cdk.CfnOutput(this, "curatedBucketName", {
      value: this.curatedBucket.bucketName,
    });
    new cdk.CfnOutput(this, "archiveBucket", {
      value: this.archiveBucket.bucketName,
    });
    new cdk.CfnOutput(this, "scriptBucketName", {
      value: this.scriptBucket.bucketName,
    });

    // HIPAA-compliant medical database outputs
    new cdk.CfnOutput(this, "MedicalDatabaseEndpoint", {
      value: this.auroraCluster.clusterEndpoint.hostname,
      description: "HIPAA-compliant medical database cluster endpoint",
    });
    new cdk.CfnOutput(this, "MedicalDatabaseReadEndpoint", {
      value: this.auroraCluster.clusterReadEndpoint.hostname,
      description: "HIPAA-compliant medical database read endpoint",
    });
    new cdk.CfnOutput(this, "MedicalDatabaseSecretArn", {
      value: this.auroraCluster.secret!.secretArn,
      description: "ARN of the encrypted medical database credentials",
    });
    new cdk.CfnOutput(this, "DatabaseKmsKeyId", {
      value: this.databaseKmsKey.keyId,
      description: "KMS key ID for database encryption",
    });
    new cdk.CfnOutput(this, "DatabaseKmsKeyArn", {
      value: this.databaseKmsKey.keyArn,
      description: "KMS key ARN for database encryption",
    });
    new cdk.CfnOutput(this, "VpcId", {
      value: this.vpc.vpcId,
      description: "VPC ID for the medical database cluster",
    });
    new cdk.CfnOutput(this, "DatabaseSecurityGroupId", {
      value: this.databaseSecurityGroup.securityGroupId,
      description: "Security group ID for database access control",
    });
  }
}
