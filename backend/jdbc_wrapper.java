import java.sql.*;

public class jdbc_wrapper {
    public static void main(String[] args) {
        if (args.length < 4) {
            System.err.println("Usage: java jdbc_wrapper <jdbc_url> <username> <password> <query>");
            System.exit(1);
        }
        
        String jdbcUrl = args[0];
        String username = args[1];
        String password = args[2];
        String query = args[3];
        
        Connection conn = null;
        Statement stmt = null;
        ResultSet rs = null;
        
        try {
            // Load driver
            Class.forName("com.snc.db.jdbc.JDBCDriver");
            
            // Create properties with credentials
            java.util.Properties props = new java.util.Properties();
            props.setProperty("user", username);
            props.setProperty("password", password);
            
            conn = DriverManager.getConnection(jdbcUrl, props);
            System.out.println("CONNECTION_SUCCESS");
            
            // Execute query
            stmt = conn.createStatement();
            rs = stmt.executeQuery(query);
            
            // Get metadata
            ResultSetMetaData rsmd = rs.getMetaData();
            int columnCount = rsmd.getColumnCount();
            
            // Print column names
            System.out.print("COLUMNS:");
            for (int i = 1; i <= columnCount; i++) {
                System.out.print(rsmd.getColumnName(i));
                if (i < columnCount) System.out.print(",");
            }
            System.out.println();
            
            // Print rows
            while (rs.next()) {
                System.out.print("ROW:");
                for (int i = 1; i <= columnCount; i++) {
                    String value = rs.getString(i);
                    System.out.print(value != null ? value : "NULL");
                    if (i < columnCount) System.out.print(",");
                }
                System.out.println();
            }
            
        } catch (Exception e) {
            System.err.println("ERROR: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        } finally {
            try {
                if (rs != null) rs.close();
                if (stmt != null) stmt.close();
                if (conn != null) conn.close();
            } catch (SQLException e) {
                e.printStackTrace();
            }
        }
    }
}
