#coding:utf-8
import urllib,urllib2,cookielib,re

class FriendList:
	def __init__(self):
		self.name = ""

	def login(self, email, password):
		login_page = "http://www.renren.com/ajaxLogin"
		data = {'email': email, 'password': password}
		post_data = urllib.urlencode(data)
		cj = cookielib.CookieJar()
		opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
		urllib2.install_opener(opener)

		print u"loginning"
		req = opener.open(login_page, post_data)
		req = urllib2.urlopen("http://www.renren.com/home")
		html = req.read()

		res = re.search("'ruid':'(\d+)'", html)
		if res:
			self.uid = res.group(1)
			return True
		else:
			return False

	def get_list(self):
		self.list = []
		pagenum = 0
		print "Start analyzing friend list"
		while True:
			page = "http://friend.renren.com/GetFriendList.do?curpage=" + str(pagenum) + "&id=" + str(self.uid)
			res = urllib2.urlopen(page)
			html = res.read()
			pattern = '<a href="http://www\.renren\.com/profile\.do\?id=(\d+)"><img src="http://.*" alt="[\S]*[\s]\((.*)\)" />'
			m = re.findall(pattern, html)
			if len(m) == 0:
				break
			for i in range(0, len(m)):
				userid = m[i][0]
				uname = m[i][1]
				try:
					self.list.append((userid, unicode(uname, 'utf-8')))
				except:
					a = 1
					#print uname
			pagenum += 1
		print "finished. ", len(self.list), " friends were found."
		return self.list

	def get_my_uid(self):
		return self.uid


if __name__ == "__main__":
	list = FriendList()
	list.login("sonicmisora@126.com", "xy")
	print list.get_list()