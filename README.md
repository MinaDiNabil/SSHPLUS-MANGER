# SSHPLUS

echo 'Acquire::ForceIPv4 "true";' > /etc/apt/apt.conf.d/99force-ipv4 && apt update -y && apt upgrade -y && wget -4 https://raw.githubusercontent.com/MinaDiNabil/SSHPLUS-MANGER/main/Plus && chmod 777 Plus && ./Plus


# Root Access

wget -4 https://raw.githubusercontent.com/MinaDiNabil/SSHPLUS-MANGER/main/senharoot.sh && chmod 777 senharoot.sh && ./senharoot.sh
