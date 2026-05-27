# CST-170 E2E fixture — 重現 S2-edge 觸發條件（anchor=v3、v4~v7 created_at 晚於 anchor）
# 執行：docker exec -i sf_project-sf-web-1 bundle exec rails runner /path/to/e2e_fixture_setup.rb
# E2E 頁面：http://sf.local/admin/project_management/projects/CST170E2E
pm = ProjectManagement::Project::Models
sn = "CST170E2E"
pm::Project.where(serial_number: sn).each do |p|
  vids = p.project_versions.pluck(:id)
  pm::ApprovalProcess.where(project_version_id: vids).delete_all
  pm::ProjectVersion.where(id: vids).delete_all
  p.delete
end
project = pm::Project.create!(serial_number: sn, name: "CST170 E2E 案場", alias: "E2E別名")
base = Time.zone.parse("2026-01-01 10:00:00")
statuses = {"1"=>"approved","2"=>"approved","3"=>"pending_approval","4"=>"canceled","5"=>"canceled","6"=>"canceled","7"=>"canceled"}
(1..7).each do |i|
  pm::ProjectVersion.create!(project_id: project.id, version_serial_number: i.to_s, status: statuses[i.to_s], created_at: base + i.hours, submitted_at: base + i.hours)
end
anchor = pm::ProjectVersion.joins("JOIN project_management_projects p ON p.id = project_management_project_versions.project_id").where(p: {serial_number: sn}).where.not(status: "canceled").order(:created_at).last
puts "CREATED serial=#{sn} versions=#{project.project_versions.count} anchor_vsn=#{anchor.version_serial_number}"
