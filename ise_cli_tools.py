import os,\
        re,\
        sys,\
        time,\
        yaml,\
        shutil,\
        socket,\
        random,\
        getpass,\
        logging,\
        netmiko
from threading import Thread
import queue as queue
from ftp_server import *


#
#
#
# Define Password Function
def define_password():
    password = None
    while not password:
        password = getpass.getpass('Please Enter ISE CLI Password: ')
        passwordverify = getpass.getpass('Re-enter ISE CLI Password to Verify: ')
        if not password == passwordverify:
            print('Passwords Did Not Match Please Try Again')
            password = None
    return password

def COMMANDS(counter,device_type,serverList,outputList,FTP_ADDR,FTP_USER,FTP_PASS):
    while not serverList.empty():
        device = deviceList.get_nowait()
        server = device['server']
        username = device['user']
        password = device['Pass']
        # Netmiko Device Type
        device_type = 'linux'

        try:

            # Connection Break
            counter = len(devices)-deviceList.qsize()
            print('\n['+str(counter)+'] Connecting to: '+device+'\n')
            outputList.put('\n['+str(counter)+'] Connecting to: '+device+'\n')
            # Connection Handler
            connection = netmiko.ConnectHandler(ip=server, device_type=device_type, username=username, password=password, global_delay_factor=6)

            # Enter App Config ISE
            output = connection.send_command('application config ise', expect_string=r'\[0\]Exit')
            output = connection.send_command('16', expect_string=r'\[0\]Exit')
            filename = re.search(r'FullReport.*\.csv',output).group()
            output = connection.send_command('0',expect_string=r'\#')
            output = connection.send_command(f'crypto host_key add host {FTP_ADDR}',expect_string=r'\#')

            #TODO: Add IF Statement for  FTP vs SFTP
            output = connection.send_command(f'copy disk:/{filename} sftp://{FTP_ADDR}',expect_string=r'Username\:')
            output = connection.send_command(f'{FTP_USER}',expect_string=r'Password\:')
            output = connection.send_command(f'{FTP_PASS}',expect_string=r'\#')
            output = connection.send_command(f'delete disk:/{filename}',expect_string=r'\#')








            outputList.put(('!\n['+str(counter)+'] PASSWORD CHANGE: PASSWORD CHANGE COMPLETED - '+device+'\n!'))
            try:
                connection.disconnect()
            except OSError:
                pass
            except:
                outputList.put(('\n!'+'\n!'+'\n['+str(counter)+'] PASSWORD CHANGE: DISCONNECT ERROR - '+device+'\n!'+'\n!'))

        except:    # exceptions as exceptionOccured:
            outputList.put(('\n!'+'\n!'+'\n['+str(counter)+'] PASSWORD CHANGE: CONNECTION ERROR - '+device+'\n!'+'\n!'))

    # Sending None to outputList as to delineate when a device has completed
    outputList.put(None)
    return









def EndpointReport(server,user,Pass):
    # FTP Mode
    sftp_mode = True
    while True:
        sftp = input('Would you like to use SFTP or FTP to transfer reports? [SFTP/ftp]: ').lower()
        if sftp in (['sftp','sft','sf','s']):
            break
        elif sftp in (['ftp','ft','f']):
            sftp_mode = False
            break

    # ISE PAN Dictionary
    PAN_Dict = {}
    PAN_Dict.update({1:{'server':server,'user':user,'Pass':Pass}})
    count = 1
    add = True
    while add:
        count +=1
        Add = input('Would You Like To Add Other ISE PANs? [y/N]: ').lower()
        if Add in (['yes','ye','y']):
                Test = False
                while not Test:
                    # Request FMC server FQDN
                    serverA = input('Please Enter ISE fqdn: ').lower().strip()

                    # Validate FQDN
                    if server[-1] == '/':
                        server = server[:-1]
                    if '//' in server:
                        server = server.split('//')[-1]

                    # Perform Test Connection To FQDN
                    s = socket.socket()
                    print(f'Attempting to connect to {serverA} on port 22')
                    try:
                        s.connect((server, 22))
                        print(f'Connecton successful to {serverA} on port 22')
                        s.close()
                        Test = True
                        PAN_Dict.update({count:{'server':serverA,'user':user,'Pass':Pass}})
                        User = input('Do you need to add a different username and password for this PAN? [y/N]: ').lower()
                        if User in (['yes','ye','y']):
                            userA = input('Please Enter ISE CLI Username: ').lower().strip()
                            PassA = define_password()
                            PAN_Dict[count]['user'] = userA
                            PAN_Dict[count]['Pass'] = PassA
                    except Exception:
                        print(f'Connection to {serverA} on port 22 failed:  {traceback.format_exc()}\n\n')
        else:
            add = False


    # Define Threading Queues
    NUM_THREADS = 20
    serverList = queue.Queue()
    outputList = queue.Queue()

    if len(devices) < NUM_THREADS:
        NUM_THREADS = len(devices)
    for key,value in PAN_Dict.items():
        deviceList.put(value)


    # Random Generated Output
    outputDirectory = ''
    outputFileName = ''
    for i in range(6):
        outputDirectory += chr(random.randint(97,122))
    outputDirectory += '/'
    if not os.path.exists(outputDirectory):
        os.makedirs(outputDirectory)
    for i in range(6):
        outputFileName += chr(random.randint(97,122))
    outputFileName += '.txt'

    # Start FTP Service
    Dir = os.getcwd()
    try:
        if sftp_mode:
            SFTP = SftpServer(Dir)
            SFTP.start()
            FTP_USER = SFTP.user
            FTP_PASS = SFTP.Pass
            FTP_ADDR = SFTP.Addr
        else:
            FTP = FtpServer(Dir)
            FTP.start()
            FTP_USER = FTP.user
            FTP_PASS = FTP.Pass
            FTP_ADDR = FTP.Addr
    except:
        print(f'Failed to start SFTP/FTP service:  {traceback.format_exc()}\n\n')
        return


    counter = 0
    # loop for devices
    for i in range(NUM_THREADS):
        Thread(target=COMMANDS, args=(counter,device_type,serverList,outputList,FTP_ADDR,FTP_USER,FTP_PASS)).start()
        time.sleep(1)

    # Stop FTP Service
    if sftp_mode:
        SFTP.stop()
    else:
        FTP = FtpServer(Dir)
        FTP.stop()

    with open(outputFileName,'w') as outputFile:
        numDone = 0
        while numDone < NUM_THREADS:
            result = outputList.get()
            if result is None:
                numDone += 1
            else:
                outputFile.write(result)
    return













#
#
#
# Run Script if main
if __name__ == '__main__':
    #
    #
    #
    # Initial input request
    print ('''
***********************************************************************************************
*                                                                                             *
*                   Cisco ISE CLI Tools (Written for Python 3.6+)                             *
*                                                                                             *
***********************************************************************************************
''')

    Test = False
    while not Test:
        # Request FMC server FQDN
        server = input('Please Enter ISE fqdn: ').lower().strip()

        # Validate FQDN
        if server[-1] == '/':
            server = server[:-1]
        if '//' in server:
            server = server.split('//')[-1]

        # Perform Test Connection To FQDN
        s = socket.socket()
        print(f'Attempting to connect to {server} on port 22')
        try:
            s.connect((server, 22))
            print(f'Connecton successful to {server} on port 22')
            Test = True
            s.close()
        except Exception:
            print(f'Connection to {server} on port 22 failed:  {traceback.format_exc()}\n\n')
            sys.exit()
    # Request User/Pass
    user = input('Please Enter ISE CLI Username: ').lower().strip()
    Pass = define_password()

    print ('''
***********************************************************************************************
*                                                                                             *
* TOOLS AVAILABLE:                                                                            *
*                                                                                             *
*  1. Download Endpoint Report                                                                *
*                                                                                             *
*  2. Password change for all ISE nodes                                                       *
*                                                                                             *
***********************************************************************************************
''')

    #
    #
    #
    # Run script until user cancels
    while True:
        Script = False
        while not Script:
            script = input('Please Select Script: ')
            if script == '1':
                Script = True
                EndpointReport(server,user,Pass)
            elif script == '2':
                Script = True
                PolicyDownload(config)
            elif script == '3':
                Script = True
                PolicyReport(config)
            else:
                print('INVALID ENTRY... ')

        # Ask to end the loop
        print ('''
***********************************************************************************************
*                                                                                             *
* TOOLS AVAILABLE:                                                                            *
*                                                                                             *
*  1. Download Endpoint Report                                                                *
*                                                                                             *
*  2. Password change for all ISE nodes                                                       *
*                                                                                             *
***********************************************************************************************
''')
        Loop = input('*\n*\nWould You Like To use another tool? [y/N]: ').lower()
        if Loop not in (['yes','ye','y','1','2','3','4']):
            break







