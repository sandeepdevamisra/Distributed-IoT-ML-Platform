import docker
import json
import logging
import subprocess

logging.basicConfig(level=logging.INFO,filename='dynamic_build.log',filemode='w')

logging.info('Reading config files')
services = json.loads(open('services.json').read())
servers = json.loads(open('platform_config.json').read())
dynamic_servers = json.loads(open('dynamic_servers.json').read())


def build(host,path,image_tag,container_name,config_path):
    logging.info('Connecing to ' + host)
    client = docker.DockerClient(base_url=host)
    logging.info('Connected to Docker')
    logging.info('Building ' + image_tag)
    client.images.build(path=path, tag=image_tag)
    logging.info('Built image: ' + image_tag)
    try:
        container = client.containers.get(container_name)
        logging.info('Container exists, stopping')
        container.stop()
        logging.info('Removing container: ' + container_name)
        container.remove()
    except:
        logging.info('Container does not exist')
    logging.info('Creating container: ' + container_name)
    try:
        container_config_path = f'/{container_name}/config.json'
        if container_name == 'deployer' or container_name == 'monitor_logger' :
            client.containers.run(image_tag,name=container_name, detach=True, network='host', volumes={'/var/run/docker.sock': {'bind': '/var/run/docker.sock', 'mode': 'rw'},
            config_path: {'bind': container_config_path, 'mode': 'rw'}})
        elif container_name == "monitor_ha":
            client.containers.run(image_tag,name=container_name, detach=True, network='host', volumes={f"/home/{servers['master']['user']}/.ssh": {'bind': '/root/.ssh', 'mode': 'rw'},
            config_path: {'bind': container_config_path, 'mode': 'rw'}})
        else:
            client.containers.run(image_tag,name=container_name, detach=True, network='host',
                                  volumes={config_path: {'bind': container_config_path, 'mode': 'rw'}})
    except Exception as e:
        logging.info('Error: ' + str(e))
    logging.info('Started ' + container_name)


def generate_service_config():
    logging.info('Generating service config')
    config = json.loads(open('../config.json').read())
    platform_config = json.loads(open('platform_config.json').read())
    for worker in dynamic_servers['workers']:
        temp = {}
        temp['name'] = worker['user']
        temp['ip'] = worker['ip']
        config['workers'].append(temp)
        platform_config['workers'].append(temp)
    
    logging.info('Writing config')
    with open('../config.json', 'w') as f:
        json.dump(config, f, indent=4)
    with open('platform_config.json', 'w') as f:
        json.dump(platform_config, f, indent=4)
    cmd = 'scp ../config.json ' + servers['master']['user'] + '@' + servers['master']['ip'] + ':~/'
    logging.info('Copyied config to master')
    subprocess.call(cmd, shell=True)
    logging.info('Updating config.json')
    for service in services['services']:
        path = '../' + service['name'] + '/' + service['name'] + '/config.json'
        with open(path, 'w') as outfile:
            json.dump(config, outfile)
        logging.info('Update config ' + path)
    
def restart_services():
    logging.info('Restarting services')
    host = 'ssh://' + servers['master']['user'] + '@' + servers['master']['ip']
    logging.info('Connecting to ' + host)
    client = docker.DockerClient(base_url=host)
    logging.info('Connected to Docker')
    services = ['deployer_master','monitor_ha','monitor_log_aggregator','load_balancer']
    for service in services:
        container = client.containers.get(service)
        logging.info('Restarting ' + service)
        container.restart()
        logging.info('Restarted ' + service)
    logging.info('Updating haproxy config')
    cmd = 'python3 config_haproxy.py dynamic_servers.json'
    subprocess.call(cmd, shell=True)
    logging.info('Copy haproxy config to master')
    cmd = 'scp haproxy.cfg ' + servers['master']['user'] + '@' + servers['master']['ip'] + ':~/'
    subprocess.call(cmd, shell=True)
    logging.info('Restarting haproxy')
    cmd = 'ssh ' + servers['master']['user'] + '@' + servers['master']['ip'] + ' "sudo mv haproxy.cfg /etc/haproxy/haproxy.cfg && sudo systemctl restart haproxy"'
    subprocess.call(cmd, shell=True)
    
    
    
def start_service():
    generate_service_config()
    logging.info('Starting service')
    for service in services['services']:
        image_name = f'{service["name"]}:{service["version"]}'
        # host = 'unix://var/run/docker.sock'
        if service['name'] == 'deployer' or service['name'] == 'monitor_logger'  or service['name'] == 'system_monitor':
            for worker in dynamic_servers['workers']:
                host = 'ssh://' + worker['user'] + '@' + worker['ip'] 
                data = json.load(open('../config.json'))
                data['host_ip'] = worker['ip']
                data['host_name'] = worker['user']
                with open('../config.json', 'w') as outfile:
                    json.dump(data, outfile)
                logging.info('Updating config.json')
                cmd = 'scp ../config.json ' + worker['user'] + '@' + worker['ip'] + ':~/'
                logging.info('Copying config to worker')
                subprocess.call(cmd, shell=True)
                config_path = f'/home/{worker["user"]}/config.json'
                build(host,service['path'],image_name,service['name'],config_path)
        
    logging.info('new servers added')
    restart_services()
    logging.info('Dynamic scaling complete')

start_service()
