from storage import Storage

info = {}
info["piece_length"] = 524288
info["length"] = 524288 * 8
st = Storage(info)

print("is all piece received: ", st.is_all_piece_received())
for i in range(8):
	for j in range(32):
		st.push(i, j*16*1024, "sdfsdfsdf")
print("is all piece received: ", st.gen_priority_list())
print("is all piece received: ", st.is_all_piece_received())
