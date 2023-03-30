from __future__ import annotations
from dataclasses import dataclass, field
import sys
import jinja2
import itertools

@dataclass
class Network:
    vpc: VPC = None
    elements: list = field(default_factory=list)
    edges: list = field(default_factory=list)
    def get_jinja_info(self):
        return ['pub','','','']
    def get_elements(self):
        return self.elements + self.edges + [self.vpc]

@dataclass
class VPC:
    zones: list = field(default_factory=list)
    def get_jinja_info(self):
        return ['vpc','','','']
    def get_elements(self):
        return self.zones

@dataclass
class Zone:
    name: str
    subnets: list = field(default_factory=list)
    elements: list = field(default_factory=list)
    securityGroups: list = field(default_factory=list)
    def get_jinja_info(self):
        return ['zone',self.name,'','']
    def get_elements(self):
        return self.subnets + self.elements + self.securityGroups

@dataclass
class Subnet:
    name: str
    IP: str
    Key: str
    elements: list = field(default_factory=list)
    def get_jinja_info(self):
        return ['subnet',self.name,self.IP, self.Key]
    def get_elements(self):
        return self.elements

@dataclass
class SecurityGroup:
    name: str
    elements: list = field(default_factory=list)
    def get_jinja_info(self):
        return ['sg',self.name,'','']
    def get_elements(self):
        return []

@dataclass
class Element:
    name: str
    type: str
    def get_jinja_info(self):
        return [self.type,self.name,'','']
    def get_elements(self):
        return []

@dataclass
class Edge:
    src: object
    dst: object
    dir: str
    label: str
    geometry: str = ''
    def get_jinja_info(self):
        return [self.dir, self.src.id, self.dst.id, self.label]
    def get_elements(self):
        return []


connections = [
    ('vsi3a-ky[10.240.30.5], vsi1-ky[10.240.10.4],  All Connections'),
    ('vsi3b-ky[10.240.30.4], vsi1-ky[10.240.10.4],  All Connections'),
    ('vsi3b-ky[10.240.30.4], vsi2-ky[10.240.20.4],  TCP 1-65535'),
    ('vsi3b-ky[10.240.30.4], vsi3a-ky[10.240.30.5],  All Connections'),
    ('vsi2-ky[10.240.20.4], vsi1-ky[10.240.10.4],  All Connections'),
    ('vsi2-ky[10.240.20.4], vsi3b-ky[10.240.30.4],  TCP 1-65535'),
    ('vsi1-ky[10.240.10.4], 161.26.0.0/16, UDP 1-65535'),
    ('vsi1-ky[10.240.10.4], 142.0.0.0/8, ICMP 0-255'),
    ('vsi1-ky[10.240.10.4], 143.0.0.0/8, ICMP 0-255'),
    ('vsi2-ky[10.240.20.4], 142.0.0.0/8, ICMP 0-255'),
    ('147.235.219.206/32, vsi2-ky[10.240.20.4],  TCP 22')
]

def build_graph():
    network = Network()
    vpc = VPC()
    us_south = Zone('us-south-1')
    subnet1 = Subnet('subnet1', '10.240.10.0/24', 'ACL1')
    subnet2 = Subnet('subnet2', '10.240.20.0/24', 'ACL2')
    subnet3 = Subnet('subnet3', '10.240.30.0/24', 'ACL3')
    securityGroup1 = SecurityGroup('sg1')
    securityGroup2 = SecurityGroup('sg2')
    securityGroup3 = SecurityGroup('sg3')
    vsi1 = Element('vsi1', 'vsi')
    vsi2 = Element('vsi2', 'vsi')
    vsi3a = Element('vsi3a', 'vsi')
    vsi3b = Element('vsi3b', 'vsi')
    public_gw = Element('public_gw', 'gateway')
    db_gw = Element('db_endpoint_gw', 'gateway')
    floating_point_ip = Element('52.118.188.231', 'floating_point')
    internet1 = Element('142.0.0.0/8', 'internet')
    internet2 = Element('143.0.0.0/8', 'internet')
    user = Element('147.235.219.206/32', 'user')

    network.parent = None
    network.vpc = vpc

    network.elements.append(internet1)
    network.elements.append(internet2)
    network.elements.append(user)

    vpc.zones.append(us_south)

    us_south.subnets.append(subnet1)
    us_south.subnets.append(subnet2)
    us_south.subnets.append(subnet3)

    us_south.securityGroups.append(securityGroup1)
    us_south.securityGroups.append(securityGroup2)
    us_south.securityGroups.append(securityGroup3)

    us_south.elements.append(public_gw)

    subnet1.elements.append(vsi1)

    subnet2.elements.append(vsi2)
    subnet2.elements.append(floating_point_ip)

    subnet3.elements.append(vsi3a)
    subnet3.elements.append(vsi3b)
    subnet3.elements.append(db_gw)

    securityGroup1.elements.append(vsi1)
    securityGroup2.elements.append(vsi2)
    securityGroup2.elements.append(vsi3b)
    securityGroup2.elements.append(floating_point_ip)
    securityGroup3.elements.append(vsi3a)
    securityGroup3.elements.append(db_gw)

    network.edges.append(Edge(vsi1, public_gw, 'diredge',''))
    network.edges.append(Edge(public_gw, internet1, 'diredge','ICMP'))
    network.edges.append(Edge(public_gw, internet2, 'diredge','ICMP'))
    network.edges.append(Edge(floating_point_ip, internet2, 'diredge','ICMP'))
    network.edges.append(Edge(user, floating_point_ip, 'diredge','TCP 22'))
    network.edges.append(Edge(vsi2, vsi1, 'diredge',''))
    network.edges.append(Edge(vsi2, vsi3b, 'undiredge','TCP'))
    network.edges.append(Edge(vsi3b, vsi1, 'diredge',''))
    network.edges.append(Edge(vsi3b, vsi3a, 'diredge',''))
    network.edges.append(Edge(vsi3b, db_gw, 'diredge',''))
    network.edges.append(Edge(db_gw, vsi1, 'diredge',''))
    network.edges.append(Edge(vsi3a, vsi1, 'diredge',''))

    network.geometry = 'x="80" y="80" width="1440" height="1000"'
    vpc.geometry = 'x="160" y="40" width="1200" height="920" '
    us_south.geometry = 'x="40" y="40" width="1000" height="840" '
    subnet1.geometry = 'x="160" y="40" width="320" height="320" '
    subnet2.geometry = 'x="160" y="400" width="320" height="320" '
    subnet3.geometry = 'x="520" y="40" width="320" height="680" '
    securityGroup1.geometry = 'x="240" y="120" width="160" height="160"'
    securityGroup2.geometry = 'x="200" y="480" width="560" height="160"'
    securityGroup3.geometry = 'x="560" y="120" width="240" height="160"'
    vsi1.geometry = 'x="130" y="130" width="60" height="60"'
    vsi2.geometry = 'x="130" y="130" width="60" height="60"'
    vsi3a.geometry = 'x="70" y="130" width="60" height="60"'
    vsi3b.geometry = 'x="130" y="490" width="60" height="60"'
    public_gw.geometry = 'x="50" y="240" width="60" height="60"'
    db_gw.geometry = 'x="190" y="130" width="60" height="60"'
    floating_point_ip.geometry = 'x="70" y="130" width="60" height="60"'
    internet1.geometry = 'x="50" y="240" width="60" height="60"'
    internet2.geometry = 'x="50" y="360" width="60" height="60"'
    user.geometry = 'x="50" y="480" width="60" height="60"'


    return network


id_counter = 100
def set_ids(me):
    global id_counter
    me.id = id_counter
    me.parent_id = me.parent.id if me.parent else ''
    id_counter += 5
    for child in me.get_elements():
        child.parent = me
        set_ids(child)


def get_jinja_info(me):
    my_info = me.get_jinja_info()
    my_info = [me.id, me.parent_id] + my_info + [me.geometry]
    children_info = list(itertools.chain(*[get_jinja_info(child) for child in me.get_elements()]))
    return [my_info] + children_info

if __name__ == "__main__":

    file_name = sys.argv[1]
    templateLoader = jinja2.FileSystemLoader(searchpath='./')
    templateEnv = jinja2.Environment(loader=templateLoader)
    template = templateEnv.get_template(file_name)

    network = build_graph()
    set_ids(network)
    jinja_info = get_jinja_info(network)
    outputText = template.render(elements=jinja_info)
    with open('out.drawio', 'w') as f:
        f.write(outputText)
