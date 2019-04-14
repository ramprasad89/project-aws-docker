import boto3
import json

def create_security_group(client, config, group_name, port_to_enable):
    security_group = client.create_security_group(GroupName=group_name,
                                                  VpcId=config['VPC']['vpcId'],
                                                  Description='security group for my application')
    for port in port_to_enable:
        client.authorize_security_group_ingress(GroupId=security_group['GroupId'],
                                                IpPermissions=[{'FromPort': port, 'IpProtocol': 'tcp', 'ToPort': port, 'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': 'Allows http port'}]}],
                                                DryRun=False)
    print("Security Group created. ID: {}".format(security_group['GroupId']))
    return security_group['GroupId']

def create_launch_configuration(client, config, security_group_id):
    config_name = config['launch_configuration']['config_name']
    key_name = config['launch_configuration']['key_name']
    user_data = '''#!/bin/bash
    cd /home/core
    docker build -t 'appserver:latest' https://github.com/ramprasad89/project-aws-docker.git
    docker run -d -p 80:80 -v /home/core/logs:/var/log/httpd appserver'''
    client.create_launch_configuration(LaunchConfigurationName=config_name,
                                       ImageId=config['Instances']['imageId'],
                                       InstanceType=config['Instances']['instanceType'],
                                       KeyName=key_name,
                                       InstanceMonitoring={'Enabled': False},
                                       UserData=user_data,
                                       SecurityGroups=[security_group_id])
    print("Launch Configuration Created. Name: {}".format(config_name))

def create_app_lb(client, config, security_group_id):
    subnets = [config['VPC']['subnet']['subnet1_us-east-1a'], config['VPC']['subnet']['subnet2_us-east-1b']]
    response = client.create_load_balancer(Name=config['load_balancer']['load_balancer_name'],
                                           Type='application',
                                           IpAddressType='ipv4',
                                           Scheme='internet-facing',
                                           Subnets=subnets,
                                           SecurityGroups=[security_group_id])
    print("Application Load Balancer Created. Arn: {}".format(response['LoadBalancers'][0]['LoadBalancerArn']))
    return response

def create_target_groups(client, config, group_name):
    response = client.create_target_group(Name=group_name,
                                          Protocol='HTTP',
                                          Port=80,
                                          VpcId=config['VPC']['vpcId'],
                                          TargetType='instance')
    print("Target Group Created. Arn: {}".format(response['TargetGroups'][0]['TargetGroupArn']))
    return response['TargetGroups'][0]['TargetGroupArn']


def create_auto_scaling_group(client, config, targetgrouparn):
    vpcidentifiers="{}, {}".format(config['VPC']['subnet']['subnet1_us-east-1a'], config['VPC']['subnet']['subnet2_us-east-1b'])
    client.create_auto_scaling_group(AutoScalingGroupName=config['AutoScaling']['group_name'],
                                     LaunchConfigurationName=config['launch_configuration']['config_name'],
                                     MinSize=2,
                                     MaxSize=2,
                                     DesiredCapacity=2,
                                     AvailabilityZones=config['load_balancer']['az'],
                                     VPCZoneIdentifier=vpcidentifiers,
                                     TargetGroupARNs=targetgrouparn)
    print("Autoscaling Group Created.")

def create_alb_listeners(client, target_group_arn, alb_arn):
    response = client.create_listener(LoadBalancerArn=alb_arn,
                                      Protocol='HTTP',
                                      Port=80,
                                      DefaultActions=[{
                                          'Type': 'forward',
                                          'TargetGroupArn': target_group_arn
                                      }
                                      ])
    return response['Listeners'][0]['ListenerArn']

def listener_rule(client, target_group_arn, listener_arn):
    response = client.create_rule(ListenerArn=listener_arn,
                                   Conditions=[{
                                       'Field': 'path-pattern',
                                       'Values': ['/'],
                                   }],
                                   Priority=1,
                                   Actions=[{
                                       'Type': 'forward',
                                       'TargetGroupArn': target_group_arn
                                   }])
    print("Listener Rule Created. Arn: {}".format(response['Rules'][0]['RuleArn']))

if __name__ == '__main__':
    with open('config.json', 'r') as read_file:
        config = json.load(read_file)
    session = boto3.Session(profile_name=config['aws']['profile'], region_name=config['aws']['region'])
    client = session.client('ec2')
    client1 = session.client('autoscaling')
    client2 = session.client('elbv2')

    #create security group for ec2 and alb
    ec2_security_group_id = create_security_group(client, config, 'ec2_security_group', config['launch_configuration']['port_to_enable'])
    alb_security_group_id = create_security_group(client, config, 'alb_security_group', config['load_balancer']['port_to_enable'])

    #create launch configuration
    create_launch_configuration(client1, config, ec2_security_group_id)

    #create target groups
    target_group_arn1 = create_target_groups(client2, config, 'AppServer1')
    target_group_arn2 = create_target_groups(client2, config, 'AppServer2')

    #create alb
    alb = create_app_lb(client2, config, alb_security_group_id)
    alb_arn = alb['LoadBalancers'][0]['LoadBalancerArn']

    #create alb listener and listener rule
    listener_arn = create_alb_listeners(client2, target_group_arn1, alb_arn)
    listener_rule(client2, target_group_arn2, listener_arn)

    #create asg
    targetgrouparn=[target_group_arn1, target_group_arn2]
    create_auto_scaling_group(client1, config, targetgrouparn)

    print("#############################################")
    print("Access the site using alb dnsname after asg creates the instances: {}".format(alb['LoadBalancers'][0]['DNSName']))
    print("#############################################")
