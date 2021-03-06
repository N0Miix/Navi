import click
from .database import new_db_connection
from .api_wrapper import request_data
from .tag_helper import update_tag, confirm_tag_exists
from sqlite3 import Error




@click.command(help="Create a Tag Category/Value Pair")
@click.option('--c', default='', help="Create a Tag with the following Category name")
@click.option('--v', default='', help="Create a Tag Value; requires --c and Category Name or UUID")
@click.option('--d', default='This Tag was created/updated by navi', help="Description for your Tag")
@click.option('--plugin', default='', help="Create a tag by plugin ID")
@click.option('--name', default='', help="Create a Tag by the text found in the Plugin Name")
@click.option('--group', default='', help="Create a Tag based on a Agent Group")
@click.option('--output', default='', help="Create a Tag based on the text in the output. Requires --plugin")
@click.option('--port', default='', help="Create a Tag based on Assets that have a port open.")
def tag(c, v, d, plugin, name, group, output, port):
    # Generator to split IPs into 2000 IP chunks
    def chunks(l, n):
        for i in range(0, len(l), n):
            yield l[i:i + n]

    # start a blank list; IP list is due to a bug
    tag_list = []
    ip_list = ""

    if c == '':
        print("Category is required.  Please use the --c command")

    if v == '':
        print("Value is required. Please use the --v command")

    if plugin:
        try:
            database = r"navi.db"
            conn = new_db_connection(database)
            with conn:
                cur = conn.cursor()
                # See if we want to refine our search by the output found in this plugin
                if output != "":
                    cur.execute("SELECT asset_ip, asset_uuid, output from vulns where plugin_id='" + plugin + "' and output LIKE '%" + output + "%';")
                else:
                    cur.execute("SELECT asset_ip, asset_uuid, output from vulns where plugin_id=%s;" % plugin)

                plugin_data = cur.fetchall()
                for x in plugin_data:
                    ip = x[0]
                    uuid = x[1]
                    # ensure the ip isn't already in the list
                    if ip not in tag_list:
                        tag_list.append(uuid)  # update functionality requires uuid.  Only using IP until API bug gets fixed
                        ip_list = ip_list + "," + ip
                    else:
                        pass
        except Error:
            pass

    if port != '':
        database = r"navi.db"
        conn = new_db_connection(database)
        with conn:
            cur = conn.cursor()
            cur.execute("SELECT * from vulns where port=" + port + " and (plugin_id='11219' or plugin_id='14272' or plugin_id='14274' or plugin_id='34220' or plugin_id='10335');")

            data = cur.fetchall()

            try:
                for vulns in data:
                    ip = vulns[1]
                    ip_list = ip_list + "," + ip
            except ValueError:
                pass

    if name != '':
        try:
            database = r"navi.db"
            conn = new_db_connection(database)
            with conn:
                cur = conn.cursor()
                cur.execute("SELECT asset_ip, asset_uuid, output from vulns where plugin_name LIKE '%" + name + "%';")

                plugin_data = cur.fetchall()
                for x in plugin_data:
                    ip = x[0]
                    uuid = x[1]
                    if ip not in tag_list:
                        tag_list.append(uuid)
                        ip_list = ip_list + "," + ip
                    else:
                        pass
        except Error:
            pass

    if group != '':
        # Updating tags is only allowed via tenable ID(UUID); However you can't grab the UUID from the Agent URI
        # Need to research a better solution for this problem.  Possibly just deleting the tag.
        try:
            querystring = {"limit": "5000"}
            group_data = request_data('GET', '/scanners/1/agent-groups')
            for agent_group in group_data['groups']:
                group_name = agent_group['name']
                group_id = agent_group['id']

                if group_name == group:
                    data = request_data('GET', '/scanners/1/agent-groups/' + str(group_id) + '/agents', params=querystring)
                    ip_list = ''

                    for agent in data['agents']:
                        ip_address = agent['ip']
                        uuid = agent['uuid']
                        ip_list = ip_list + "," + ip_address
                        tag_list.append(uuid)
        except Error:
            print("You might not have agent groups, or you are using Nessus Manager.  ")

    if ip_list == '':
        print("\nYour tag resulted in 0 Assets, therefore the tag wasn't created\n")
    else:
        answer = confirm_tag_exists(c, v)
        if answer == 'yes':
            # check to see if the list is over 2000
            if len(tag_list) > 1999:
                # break the list into 2000 IP chunks
                for chunks in chunks(tag_list, 1999):
                    update_tag(c, v, chunks)
            else:
                update_tag(c, v, tag_list)
        else:
            if len(tag_list) > 1999:
                try:
                    payload = {"category_name": str(c), "value": str(v), "description": str(d)}
                    data = request_data('POST', '/tags/values', payload=payload)
                    value_uuid = data["uuid"]
                    cat_uuid = data['category_uuid']
                    print("\nI've created your new Tag - {} : {}\n".format(c, v))
                    print("The Category UUID is : {}\n".format(cat_uuid))
                    print("The Value UUID is : {}\n".format(value_uuid))
                    print("Your Tag list was over 2000 IPs.  Splitting the IPs into chunks and updating the tags now")
                    for chunks in chunks(tag_list, 1999):
                        update_tag(c, v, chunks)

                    print(str(len(tag_list)) + " IPs added to the Tag")
                except Exception as E:
                    print("Duplicate Tag Category: You may need to delete your tag first\n")
                    print("We could not confirm your tag name, is it named weird?\n")
                    print(E)
            else:

                try:
                    payload = {"category_name": str(c), "value": str(v), "description": str(d), "filters": {"asset": {"and": [{"field": "ipv4", "operator": "eq", "value": str(ip_list[1:])}]}}}
                    data = request_data('POST', '/tags/values', payload=payload)
                    try:
                        value_uuid = data["uuid"]
                        cat_uuid = data['category_uuid']
                        print("\nI've created your new Tag - {} : {}\n".format(c, v))
                        print("The Category UUID is : {}\n".format(cat_uuid))
                        print("The Value UUID is : {}\n".format(value_uuid))
                        print(str(len(tag_list)) + " IPs added to the Tag")
                    except Exception as E:
                        print("Duplicate Tag Category: You may need to delete your tag first\n")
                        print("We could not confirm your tag name, is it named weird?\n")
                        print(E)
                except:
                    print("Duplicate Category")
