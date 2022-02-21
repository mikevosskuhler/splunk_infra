from aws_cdk import (
    # Duration,
    Stack,
    aws_ec2 as ec2,
    aws_route53 as route53
)
from constructs import Construct

class SplunkInfraStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        '''
        1 master node --> idx (8089); lm (8089)
        1 deployer --> sh (8089); lm (8089)
        3 sh --> mn (8089); idx (8089); sh (8089; 8191; 9200)
        3 indexers --> mn (8089); idx (8089; 9100); lm (8089) 
        1 hf --> idx (9997); lm (8089)
        1 license server 
        1 monitoring console --> all (8089)
        '''
        vpc = ec2.Vpc(self, "MainVpc",
                subnet_configuration=[
                ec2.SubnetConfiguration(
                name="public-subnet",
                subnet_type=ec2.SubnetType.PUBLIC
                )],
                max_azs=1
        )
        mn_sg = ec2.SecurityGroup(self, 'mn_sg', vpc = vpc)
        dp_sg = ec2.SecurityGroup(self, 'dp_sg', vpc = vpc)
        sh_sg = ec2.SecurityGroup(self, 'sh_sg', vpc = vpc)
        idx_sg = ec2.SecurityGroup(self, 'idx_sg', vpc = vpc)
        hf_sg = ec2.SecurityGroup(self, 'hf_sg', vpc = vpc)
        lm_sg = ec2.SecurityGroup(self, 'lm_sg', vpc = vpc)
        mc_sg = ec2.SecurityGroup(self, 'mc_sg', vpc = vpc)

        # indexers SG acls
        idx_sg.connections.allow_internally(ec2.Port.tcp(9100))
        idx_sg.connections.allow_internally(ec2.Port.tcp(8089))
        mn_sg.connections.allow_from(idx_sg, ec2.Port.tcp(8089))
        lm_sg.connections.allow_from(idx_sg, ec2.Port.tcp(8089))
        
        # search heads SG acls
        sh_sg.connections.allow_internally(ec2.Port.tcp(9200))
        sh_sg.connections.allow_internally(ec2.Port.tcp(8089))
        sh_sg.connections.allow_internally(ec2.Port.tcp(8191))
        mn_sg.connections.allow_from(sh_sg, ec2.Port.tcp(8089))
        lm_sg.connections.allow_from(sh_sg, ec2.Port.tcp(8089))
        idx_sg.connections.allow_from(sh_sg, ec2.Port.tcp(8089))
        dp_sg.connections.allow_from(sh_sg, ec2.Port.tcp(8089))
        
        # Master Node SG acls
        idx_sg.connections.allow_from(mn_sg, ec2.Port.tcp(8089))
        lm_sg.connections.allow_from(mn_sg, ec2.Port.tcp(8089))
        
        # Deployer SG acls
        lm_sg.connections.allow_from(dp_sg, ec2.Port.tcp(8089))
        sh_sg.connections.allow_from(dp_sg, ec2.Port.tcp(8089))
        
        # Heavy Forwarder SG aclshf --> idx (9997); lm (8089)
        idx_sg.connections.allow_from(hf_sg, ec2.Port.tcp(8089))
        lm_sg.connections.allow_from(hf_sg, ec2.Port.tcp(8089))
        
        # monitoring console --> all (8089)
        sh_sg.connections.allow_from(mc_sg, ec2.Port.tcp(8089))
        lm_sg.connections.allow_from(mc_sg, ec2.Port.tcp(8089))
        mn_sg.connections.allow_from(mc_sg, ec2.Port.tcp(8089))
        idx_sg.connections.allow_from(mc_sg, ec2.Port.tcp(8089))
        dp_sg.connections.allow_from(mc_sg, ec2.Port.tcp(8089))
        hf_sg.connections.allow_from(mc_sg, ec2.Port.tcp(8089))
        
        # ssh and splunk GUI to the world
        sh_sg.connections.allow_from_any_ipv4(ec2.Port.tcp(8000))
        lm_sg.connections.allow_from_any_ipv4(ec2.Port.tcp(8000))
        mn_sg.connections.allow_from_any_ipv4(ec2.Port.tcp(8000))
        idx_sg.connections.allow_from_any_ipv4(ec2.Port.tcp(8000))
        dp_sg.connections.allow_from_any_ipv4(ec2.Port.tcp(8000))
        hf_sg.connections.allow_from_any_ipv4(ec2.Port.tcp(8000))
        mc_sg.connections.allow_from_any_ipv4(ec2.Port.tcp(8000))
        
        sh_sg.connections.allow_from_any_ipv4(ec2.Port.tcp(22))
        lm_sg.connections.allow_from_any_ipv4(ec2.Port.tcp(22))
        mn_sg.connections.allow_from_any_ipv4(ec2.Port.tcp(22))
        idx_sg.connections.allow_from_any_ipv4(ec2.Port.tcp(22))
        dp_sg.connections.allow_from_any_ipv4(ec2.Port.tcp(22))
        hf_sg.connections.allow_from_any_ipv4(ec2.Port.tcp(22))
        mc_sg.connections.allow_from_any_ipv4(ec2.Port.tcp(22))
        
        instance_type = ec2.InstanceType('t2.micro')
        amzn_linux = ec2.MachineImage.latest_amazon_linux(
                # These settings and more can be configured for the new AL2 instance
                generation=ec2.AmazonLinuxGeneration.AMAZON_LINUX_2,
                edition=ec2.AmazonLinuxEdition.STANDARD,
                virtualization=ec2.AmazonLinuxVirt.HVM,
                storage=ec2.AmazonLinuxStorage.GENERAL_PURPOSE
                )
                
        machines = {"sh1": sh_sg, "sh2": sh_sg, "sh3": sh_sg, 
                    "lm": lm_sg, 
                    "mn": mn_sg, 
                    "idx1": idx_sg, "idx2": idx_sg, "idx3": idx_sg, 
                    "dp": dp_sg,
                    "hf": hf_sg,
                    "mc": mc_sg
        }
        
        zone = route53.PrivateHostedZone(self, 'privateHostedZone', zone_name="vosskuhler.com", vpc=vpc)
        
        for machine in machines:
            instance = ec2.Instance(self, machine,
                                    instance_type=instance_type,
                                    machine_image=amzn_linux,
                                    vpc = vpc,
                                    security_group = machines[machine],
                                    key_name = 'mac'
                                    )
            route53.ARecord(self, machine + "_arecord",
                            zone = zone,
                            target = route53.RecordTarget.from_ip_addresses(instance.instance_private_ip),
                            record_name = machine + '.vosskuhler.com'
                            )