FROM centos:latest
MAINTAINER Ram Prasad Panda <ram082.iacr@gmail.com>
RUN yum install -y yum-plugin-ovl \
	yum update -y \
	yum install httpd -y \
	yum clean all
RUN echo "ServerName	localhost" >> /etc/httpd/conf/httpd.conf
VOLUME ["/home/core/logs", "/var/log/httpd"]
RUN echo "The Web Server is Running" > /var/www/html/index.html
EXPOSE 80

#Start httpd
CMD ["-D", "FOREGROUND"]
ENTRYPOINT ["/usr/sbin/httpd"]
